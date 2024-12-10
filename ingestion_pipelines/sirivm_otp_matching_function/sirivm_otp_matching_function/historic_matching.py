# This file is the entry point of an ECS task that performs a long-lived matching process.
# It lives alongside the lambda code for ease of development

import os
import sys
from collections.abc import Sequence

import boto3
import polars as pl
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
    avl_group: pl.LazyFrame,
) -> Sequence[AVLRecord]:
    avl_batch = (
        avl_group.filter(pl.col("group_id") == group_id).collect().row(0, named=True)
    )
    avl_list = []
    for index, _avl_id in enumerate(avl_batch["siri_vm_positions_id"]):
        avl: AVLRecord = {
            "recorded_at_time": str(avl_batch["recorded_at_time"][index]),
            "response_timestamp": str(avl_batch["response_time_stamp"][index]),
            "latitude": float(avl_batch["latitude"][index]),
            "longitude": float(avl_batch["longitude"][index]),
            "line_name": str(avl_batch["line_name"][index]),
            "operator_ref": str(avl_batch["operator_ref"][index]),
            "vehicle_ref": str(avl_batch["vehicle_ref"][index]),
            "journey_ref": str(avl_batch["journey_ref"][index]),
            "direction_ref": str(avl_batch["direction_ref"][index]),
            "date_of_journey": str(avl_batch["date_of_journey"][index]),
            "batch_id": int(avl_batch["batch_id"]),
        }

        if avl["operator_ref"] == "TFLO":
            logger.debug("Skipping TFLO")
            continue

        avl_list.append(avl)
    return avl_list


def get_timetable_data_for_group_id(
    group_id: str,
    timetable: pl.LazyFrame,
) -> Timetable | None:
    group_timetable = timetable.group_by(pl.col("group_id"))
    filtered_timetable_df = group_timetable.all().filter(
        pl.col("group_id").str.to_lowercase() == group_id,
    )

    stop_data = filtered_timetable_df.collect().row(0, named=True)

    if len(stop_data) <= 0:
        return None

    directions = set(stop_data["direction"])
    row_count = len(stop_data["stop_index"])

    timetable: dict[str, dict[str, StopDetails]] = {}
    for stop in range(row_count):
        index = group_id

        if len(directions) > 1:
            stop_direction = str(stop_data["direction"][stop])
            index += f"|{stop_direction}"

        route_details = timetable.setdefault(index, {})
        normalised_stop_index = str(len(route_details) + 1)
        route_details[normalised_stop_index] = (
            (
                float(stop_data["stop_latitude"][stop]),
                float(stop_data["stop_longitude"][stop]),
            ),
            str(stop_data["expected_departure_time"][stop]),
            int(stop_data["timetable_id"][stop]),
            str(stop_data["date_of_journey"][stop]),
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
    avl_data = pl.scan_parquet(avl_path)
    logger.info(f"Loaded avl data for {date_str}")
    avl_group = avl_data.group_by("group_id", maintain_order=True).all()
    avl_group_count = avl_group.len().collect()
    avl_group_list = avl_group_count.get_column("group_id")
    timetable = pl.scan_parquet(timetable_path)

    number_of_groups = len(avl_group_list)
    logger.info("Starting to process AVL data", number_of_groups=number_of_groups)
    batch_number = 0
    for group_id in avl_group_list:
        batch_number += 1
        logger.info(
            "Run historic matching for batch",
            group_id=group_id,
            group_number=batch_number,
            number_of_group_ids=number_of_groups,
        )
        try:
            group_avls = get_avls_for_group_id(group_id, avl_group)

            if len(group_avls) < 1:
                logger.info("No AVLs in the list")
                continue

            logger.info("Produced avl list", size=len(group_avls))

            routes_for_group_id = get_timetable_data_for_group_id(group_id, timetable)

            if routes_for_group_id is None:
                logger.info("Could not find timetable for group_id", group_id=group_id)
                continue

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
        logger.info(f"Loaded timetable for {process_date}")
        historic_matching(
            avl_path=local_avl_path,
            timetable_path=local_timetable_path,
            date_str=process_date,
        )
    except Exception:
        logger.exception("An error occurred")
        sys.exit(2)
