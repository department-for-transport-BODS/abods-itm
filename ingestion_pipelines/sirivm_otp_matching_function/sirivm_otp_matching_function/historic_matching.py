# This file is the entry point of an ECS task that performs a long-lived matching process.
# It lives alongside the lambda code for ease of development

import os
import sys
import time
from collections.abc import Mapping
from multiprocessing import Process, Queue

import boto3
import duckdb
from aws_lambda_powertools import Logger

from .client_db import TimetableDBClient
from .matcher.live_timetable_store import LiveTimetableStore
from .matcher.matching import positions_timetable_lookup
from .matcher.models import AVLRecord, StopDetails, Timetable
from .matcher.utils import timer

logger = Logger()

two_hours_secs = -7200

s3 = boto3.client("s3")


def historic_matching(avl_path: str, timetable_path: str, date_str: str) -> None:
    """
    Run historic matching

    Args:
    ----
        avl_path (str): Path to avl parquet
        timetable_path (str): Path to timetable parquet
        date_str (str): The date for historic matching

    """
    operator_queue = Queue()
    with duckdb.connect("avl_timetable.db") as conn:
        conn.execute(f"""
            CREATE TABLE avl AS
            SELECT *
            FROM '{avl_path}'
        """)  # noqa: S608 Not really sql injection
        conn.execute(f"""
            CREATE TABLE timetable AS
            SELECT *
            FROM '{timetable_path}'
        """)  # noqa: S608 Not really sql injection

        for row in conn.query(
            """
            SELECT DISTINCT a.operator_ref
            FROM timetable t
            INNER JOIN avl a ON a.group_id = t.group_id
            """,
        ).fetchall():
            operator_queue.put(row[0])
    number_of_operators = (
        operator_queue.qsize()
    )  # Should be fine since nothing is reading yet
    logger.info("Starting to process AVL data", number_of_groups=number_of_operators)
    workers = []
    num_workers = 8
    logger.info("Launching workers", num_workers=num_workers)
    for i in range(num_workers):
        worker = Process(
            target=worker_task,
            args=(date_str, number_of_operators, operator_queue, i),
        )
        worker.start()
        workers.append(worker)
    for worker in workers:
        worker.join()


def worker_task(  # noqa:C901 Don't care
    date_str: str,
    number_of_operators: int,
    operator_queue: Queue,
    worker_id: int,
) -> None:
    logger.append_keys(worker_id=worker_id)
    db_client = TimetableDBClient()
    with duckdb.connect(
        "avl_timetable.db",
        config={"access_mode": "READ_ONLY"},
    ) as process_conn:

        @timer(logger)
        def get_avls_for_operator(
            operator_ref: str,
        ) -> Mapping[str, list[AVLRecord]]:
            by_group_id = {}
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
                by_group_id.setdefault(group_id, []).append(
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
            return by_group_id

        @timer(logger)
        def get_timetable_data_for_operator(
            operator_ref: str,
        ) -> Timetable:
            stop_data = process_conn.execute(
                f"""
                SELECT
                    group_id,
                    direction,
                    stop_latitude,
                    stop_longitude,
                    expected_departure_time,
                    timetable_id,
                    date_of_journey,
                    stop_index
                FROM timetable
                WHERE split_part(group_id, '|', 1) = LOWER('{operator_ref}')
                """,
            ).fetchall()
            by_group_id = {}
            for data in stop_data:
                by_group_id.setdefault(data[0], []).append(data)
            timetable: dict[str, dict[str, StopDetails]] = {}
            for group_id, stops in by_group_id.items():
                stops.sort(key=lambda x: int(x[7]))
                directions = {rec[0] for rec in stops}
                for (
                    _,
                    direction,
                    stop_latitude,
                    stop_longitude,
                    expected_departure_time,
                    timetable_id,
                    date_of_journey,
                    _stop_index,
                ) in stops:
                    index = group_id
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
            return timetable

        while True:
            try:
                latest_operator_ref = operator_queue.get(timeout=10)
                if latest_operator_ref is None:
                    return

                logger.info(
                    "Processing operator",
                    operator_ref=latest_operator_ref,
                    initial_group_count=number_of_operators,
                    estimated_remaining_groups=operator_queue.qsize(),
                )
                operator_avls_by_group_id = get_avls_for_operator(latest_operator_ref)
                timetable_data = get_timetable_data_for_operator(latest_operator_ref)
                timetable_store = LiveTimetableStore(timetable_data)

                start_time = time.perf_counter_ns()
                try:
                    for avls in operator_avls_by_group_id.values():
                        journey_matches = []
                        stop_history = {}
                        avls.sort(key=lambda x: x["recorded_at_time"])
                        for avl in avls:
                            to_set, to_remove, stop_history = (
                                positions_timetable_lookup(
                                    timetable_store,
                                    [avl],
                                    stop_history,
                                )
                            )
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
                            None,
                            journey_matches,
                            [],
                            date_str,
                        )
                finally:
                    end_time = time.perf_counter_ns()
                    run_time = end_time - start_time
                    logger.info(
                        "Finished process_operator_data()",
                        time_in_ms=run_time / 1000000,
                        operator_journeys=len(operator_avls_by_group_id),
                        operator_timetables=len(timetable_data),
                    )
            except Exception:
                logger.exception("An error occurred when processing historic record")


if __name__ == "__main__":
    try:
        if "PROCESS_DATE" not in os.environ:
            logger.error("Environment variable PROCESS_DATE is missing.")
            sys.exit(1)

        process_date = os.environ["PROCESS_DATE"]
        logger.append_keys(PROCESS_DATE=process_date)
        process_date_parts = process_date.split("-")
        year = process_date_parts[0]
        month = process_date_parts[1].zfill(2)
        day = process_date_parts[2].zfill(2)
        s3_bucket = os.getenv("SIRIVM_BUCKET", "abods-sandbox-exporter-bucket")

        local_timetable_path = "/tmp/timetable.parquet"  # noqa: S108 intentional use of /tmp
        local_avl_path = "/tmp/avl.parquet"  # noqa: S108 intentional use of /tmp
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
        logger.info("Downloaded parquet files")
        historic_matching(
            avl_path=local_avl_path,
            timetable_path=local_timetable_path,
            date_str=process_date,
        )
    except Exception:
        logger.exception("An error occurred")
        sys.exit(2)
