# This file is the entry point of an ECS task that performs a long-lived matching process.
# It lives alongside the lambda code for ease of development

import os
import sys
from multiprocessing import Process, Queue
from queue import Empty

import boto3
import duckdb
from aws_lambda_powertools import Logger

from .client_db import TimetableDBClient
from .matcher.live_timetable_store import LiveTimetableStore
from .matcher.matching import positions_timetable_lookup
from .matcher.models import (
    StopDetails,  # noqa: TCH001, TC001 I don't mind importing types at runtime
)
from .matcher.utils import log_execution_time

logger = Logger()

two_hours_secs = -7200


def operator_worker_task(  # noqa: C901 Complexity not much of an issue here
    date_str: str,
    task_count: int,
    task_queue: Queue,
    worker_id: int,
) -> None:
    logger.append_keys(worker_id=worker_id)
    db_client = TimetableDBClient()
    with duckdb.connect(
        "avl_timetable.db",
        config={"access_mode": "READ_ONLY"},
    ) as process_conn:
        while True:
            try:
                operator_ref = task_queue.get(timeout=10)
                if operator_ref is None:  # Sentinel value to indicate no more work
                    task_queue.put(None)
                    return
            except Empty:
                logger.info("No operators available, worker exiting")
                return
            except Exception:
                logger.exception("An unexpected exception occurred")
                continue

            try:
                logger.info(
                    "Processing operator",
                    operator_ref=operator_ref,
                    initial_group_count=task_count,
                    # Potentially incorrect if another process took a value before we checked, but unlikely
                    # Also, a sentinel value is at the end, but we also just popped a value
                    estimated_remaining_groups=task_queue.qsize(),
                )

                avls_by_group_id = {}
                with log_execution_time(logger, "fetch_avls"):
                    for (
                        recorded_at_time,
                        response_time_stamp,
                        latitude,
                        longitude,
                        line_name,
                        vehicle_ref,
                        journey_ref,
                        direction_ref,
                        date_of_journey,
                        batch_id,
                        group_id,
                    ) in process_conn.execute(
                        f"""
                            SELECT
                                recorded_at_time,
                                response_time_stamp,
                                latitude,
                                longitude,
                                line_name,
                                vehicle_ref,
                                journey_ref,
                                direction_ref,
                                date_of_journey,
                                batch_id,
                                group_id
                            FROM avl
                            WHERE operator_ref = '{operator_ref}'
                        """,
                    ).fetchall():
                        avls_by_group_id.setdefault(group_id, []).append(
                            {
                                "recorded_at_time": str(recorded_at_time),
                                "response_timestamp": str(response_time_stamp),
                                "latitude": float(latitude),
                                "longitude": float(longitude),
                                "line_name": str(line_name),
                                "operator_ref": str(operator_ref),
                                "vehicle_ref": str(vehicle_ref),
                                "journey_ref": str(journey_ref),
                                "direction_ref": str(direction_ref),
                                "date_of_journey": str(date_of_journey),
                                "batch_id": int(batch_id),
                            },
                        )
                timetable: dict[str, dict[str, StopDetails]] = {}
                with log_execution_time(logger, "fetch_timetable"):
                    stop_data = process_conn.execute(
                        f"""
                            SELECT
                                group_id,
                                operator_noc,
                                direction,
                                stop_latitude,
                                stop_longitude,
                                expected_departure_time,
                                timetable_id,
                                date_of_journey,
                                stop_index
                            FROM timetable
                            WHERE operator_noc = '{operator_ref}'
                        """,
                    ).fetchall()
                    # Initially bucket by group_id, since we need to do something different if there are multiple directions within each
                    by_group_id = {}
                    for data in stop_data:
                        by_group_id.setdefault(data[0], []).append(data)

                    for group_id, stops in by_group_id.items():
                        # sort just in case duckdb returns in the wrong order
                        stops.sort(key=lambda x: int(x[7]))

                        directions = {rec[0] for rec in stops}
                        for (
                            _,
                            _operator_noc,
                            direction,
                            stop_latitude,
                            stop_longitude,
                            expected_departure_time,
                            timetable_id,
                            date_of_journey,
                            _stop_index,
                        ) in stops:
                            index = group_id
                            # If the timetable data has multiple directions, we need to separate those in this representation
                            # LiveTimetableStore will try the plain group_id first and then try with the avl direction if not found
                            if len(directions) > 1:
                                stop_direction = str(direction)
                                index += f"|{stop_direction}"

                            route_details = timetable.setdefault(index, {})
                            normalised_stop_index = str(len(route_details) + 1)
                            route_details[normalised_stop_index] = (
                                (
                                    float(stop_latitude),
                                    float(stop_longitude),
                                ),
                                str(expected_departure_time),
                                int(timetable_id),
                                str(date_of_journey),
                            )
                timetable_store = LiveTimetableStore(timetable)

                with log_execution_time(
                    logger,
                    "process_operator_data",
                    operator_journeys=len(avls_by_group_id),
                    operator_timetables=len(timetable),
                ):
                    for avls in avls_by_group_id.values():
                        # sort just in case duckdb returns in the wrong order
                        avls.sort(key=lambda x: x["recorded_at_time"])

                        journey_matches = []
                        stop_history = {}
                        for avl in avls:
                            # noqa: TD003 TODO(gps035): The matching code should have an entry point for a single avl
                            to_set, to_remove, stop_history = (
                                positions_timetable_lookup(
                                    timetable_store,
                                    [avl],
                                    stop_history,
                                )
                            )
                            # The live matching code can result in a db update that it later changes its mind about
                            # If that happens here, we can just remove any prior matches with the same timetable id,
                            # before we update the db
                            remove_timetable_ids = [
                                rec["timetable_id"] for rec in to_remove
                            ]
                            journey_matches = [
                                rec
                                for rec in journey_matches
                                if rec["timetable_id"] not in remove_timetable_ids
                            ]
                            journey_matches.extend(to_set)

                        db_client.historic_update_success(
                            None,  # We aren't using avl batches, so we need to skip the batch table update
                            journey_matches,
                            [],
                            date_str,
                        )
            except Exception:
                logger.exception("An error occurred when processing historic record")


if __name__ == "__main__":
    try:
        process_date = os.getenv("PROCESS_DATE")
        if not process_date:
            logger.error("Environment variable PROCESS_DATE is missing.")
            sys.exit(1)

        s3_bucket = os.getenv("SIRIVM_BUCKET", "abods-sandbox-exporter-bucket")

        logger.append_keys(PROCESS_DATE=process_date)

        local_timetable_path = "/tmp/timetable.parquet"  # noqa: S108 intentional use of /tmp
        local_avl_path = "/tmp/avl.parquet"  # noqa: S108 intentional use of /tmp

        with log_execution_time(logger, "parquet_download"):
            process_date_parts = process_date.split("-")
            year = process_date_parts[0]
            month = process_date_parts[1].zfill(2)
            day = process_date_parts[2].zfill(2)
            s3 = boto3.client("s3")
            s3.download_file(
                Bucket=s3_bucket,
                Key=f"historic/parquet/YYYY={year}/MM={month}/DD={day}/timetable_{year}{month}{day}.parquet",
                Filename=local_timetable_path,
            )
            s3.download_file(
                Bucket=s3_bucket,
                Key=f"historic/parquet/YYYY={year}/MM={month}/DD={day}/siri_vm_{year}{month}{day}.parquet",
                Filename=local_avl_path,
            )

        operator_queue = Queue()
        with duckdb.connect("avl_timetable.db") as conn:
            with log_execution_time(logger, "build_db"):
                conn.execute(f"""
                    CREATE TABLE avl AS
                    SELECT *
                    FROM '{local_avl_path}'
                """)  # noqa: S608 Not really sql injection
                conn.execute(f"""
                    CREATE TABLE timetable AS
                    SELECT *
                    FROM '{local_timetable_path}'
                """)  # noqa: S608 Not really sql injection

            with log_execution_time(logger, "get_operators"):
                for row in conn.query(
                    """
                        SELECT DISTINCT a.operator_ref
                        FROM timetable t
                        INNER JOIN avl a ON a.group_id = t.group_id
                        """,
                ).fetchall():
                    operator_queue.put(row[0])

        operator_count = (
            operator_queue.qsize()
        )  # Should be fine since nothing is reading yet

        operator_queue.put(None)  # Sentinel value to indicate no more work

        logger.info(
            "Starting to process AVL data",
            number_of_groups=operator_count,
        )
        workers = []
        num_workers = 8  # noqa: TD003 TODO(gps035): Should align to number of cores available
        logger.info("Launching workers", num_workers=num_workers)
        for i in range(num_workers):
            worker = Process(
                target=operator_worker_task,
                args=(process_date, operator_count, operator_queue, i),
            )
            worker.start()
            workers.append(worker)

        logger.info(
            "Spawned workers, waiting for each to exit",
            num_workers=num_workers,
        )
        for worker in workers:
            worker.join()

        logger.info("Finished processing AVL data")
    except Exception:
        logger.exception("An error occurred")
        sys.exit(2)
