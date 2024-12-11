# This file is the entry point of an ECS task that performs a long-lived matching process.
# It lives alongside the lambda code for ease of development

import os
import sys
from collections.abc import Sequence

import boto3
import duckdb
from aws_lambda_powertools import Logger

from .client_db import TimetableDBClient
from .matcher.live_timetable_store import LiveTimetableStore
from .matcher.matching import positions_timetable_lookup
from .matcher.models import AVLRecord, StopDetails, Timetable
from .matcher.utils import timer

logger = Logger()
db_client = TimetableDBClient()

two_hours_secs = -7200

s3 = boto3.client("s3")


@timer(logger)
def get_avls_for_group_id(
    group_id: str,
) -> Sequence[AVLRecord]:
    return [
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
        }
        for (
            recorded_at_time,
            response_time_stamp,
            latitude,
            longitude,
            line_name,
            operator_ref,
            vehicle_ref,
            journey_ref,
            direction_ref,
            date_of_journey,
            batch_id,
        ) in duckdb.sql(
            f"""
            SELECT
                recorded_at_time,
                response_time_stamp,
                latitude,
                longitude,
                line_name,
                operator_ref,
                vehicle_ref,
                journey_ref,
                direction_ref,
                date_of_journey,
                batch_id
            FROM avl
            WHERE group_id = '{group_id}'
            """,
        ).fetchall()
    ]


@timer(logger)
def get_timetable_data_for_group_id(
    group_id: str,
) -> Timetable:
    stop_data = duckdb.sql(
        f"""
        SELECT
            direction,
            stop_latitude,
            stop_longitude,
            expected_departure_time,
            timetable_id,
            date_of_journey
        FROM timetable
        WHERE group_id = '{group_id}'
        """,
    ).fetchall()
    directions = {rec[0] for rec in stop_data}
    timetable: dict[str, dict[str, StopDetails]] = {}
    for (
        direction,
        stop_latitude,
        stop_longitude,
        expected_departure_time,
        timetable_id,
        date_of_journey,
    ) in stop_data:
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


@timer(logger)
def historic_matching(avl_path: str, timetable_path: str, date_str: str) -> None:
    """
    Run historic matching

    Args:
    ----
        avl_path (str): Path to avl parquet
        timetable_path (str): Path to timetable parquet
        date_str (str): The date for historic matching

    """
    duckdb.sql(f"""
        CREATE TABLE avl AS
        SELECT *
        FROM '{avl_path}'
    """)  # noqa: S608 Not really sql injection
    duckdb.sql(f"""
        CREATE TABLE timetable AS
        SELECT *
        FROM '{timetable_path}'
    """)  # noqa: S608 Not really sql injection
    group_ids: list[str] = [
        row[0]
        for row in duckdb.sql(
            """
            SELECT DISTINCT a.group_id
            FROM timetable t
            INNER JOIN avl a ON a.group_id = t.group_id
            """,
        ).fetchall()
    ]
    number_of_groups = len(group_ids)
    logger.info("Starting to process AVL data", number_of_groups=number_of_groups)
    for idx, group_id in enumerate(group_ids):
        group_number = idx + 1
        logger.info(
            "Processing group_id",
            group_id=group_id,
            group_number=group_number,
            number_of_groups=number_of_groups,
        )
        try:
            group_avls = get_avls_for_group_id(group_id)

            logger.info("Produced avl list", size=len(group_avls))

            routes_for_group_id = get_timetable_data_for_group_id(
                group_id,
            )

            process_group_data(date_str, group_avls, routes_for_group_id)
        except Exception:
            logger.exception("An error occurred when processing historic record")


@timer(logger)
def process_group_data(
    date_str: str,
    group_avls: Sequence[AVLRecord],
    routes_for_group_id: Timetable,
) -> None:
    timetable_store = LiveTimetableStore(routes_for_group_id)
    total_to_set = []
    stop_history = {}
    for avl in group_avls:
        to_set, to_remove, stop_history = positions_timetable_lookup(
            timetable_store,
            [avl],
            stop_history,
        )
        remove_timetable_ids = [rec["timetable_id"] for rec in to_remove]
        total_to_set = [
            rec
            for rec in total_to_set
            if rec["timetable_id"] not in remove_timetable_ids
        ]
        total_to_set.extend(to_set)
    db_client.historic_update_success(
        None,
        total_to_set,
        [],
        date_str,
    )


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
        logger.info(f"Loaded timetable for {process_date}")
        historic_matching(
            avl_path=local_avl_path,
            timetable_path=local_timetable_path,
            date_str=process_date,
        )
    except Exception:
        logger.exception("An error occurred")
        sys.exit(2)
