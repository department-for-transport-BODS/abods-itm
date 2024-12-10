# This file is the entry point of an ECS task that performs a long-lived matching process.
# It lives alongside the lambda code for ease of development

import os
import subprocess
import sys
from collections.abc import Sequence

import boto3
import polars as pl
from aws_lambda_powertools import Logger

from .client_db import TimetableDBClient
from .matcher.historic_timetable_store import HistoricTimetableStore
from .matcher.matching import positions_timetable_lookup
from .matcher.models import AVLRecord
from .matcher.utils import timer

logger = Logger()
db_client = TimetableDBClient()

two_hours_secs = -7200

s3 = boto3.client("s3")


@timer(logger)
def validate_avl_list(
    avl_list: Sequence[AVLRecord],
    expected_batch_id: int,
) -> None:
    for avl in avl_list:
        if avl["batch_id"] != expected_batch_id:
            raise Exception("AVLs with multiple match ids retrieved")  # noqa: TRY002 - Not worth making an exception type


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
    avl_group = avl_data.group_by("batch_id", maintain_order=True)
    avl_group_count = avl_group.len().collect()
    avl_batch_id_list = avl_group_count.get_column("batch_id")
    timetable_store = HistoricTimetableStore(pl.scan_parquet(timetable_path))

    stop_history = {}
    number_of_batches = len(avl_batch_id_list)
    logger.info("Starting to process AVL data", number_of_batches=number_of_batches)
    batch_number = 0
    for batch in avl_batch_id_list:
        batch_number += 1
        logger.info(
            "Run historic matching for batch",
            batch_id=batch,
            batch_number=batch_number,
            number_of_batches=number_of_batches,
        )

        @timer(logger)
        def get_avls():
            avl_batch = (
                avl_group.all()
                .filter(pl.col("batch_id") == batch)
                .collect()
                .row(0, named=True)
            )
            avls = []
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

                avls.append(avl)
            return avls

        avl_list = get_avls()
        if len(avl_list) < 1:
            logger.info("No AVLs in the list")
            continue

        logger.info("Produced avl list", size=len(avl_list))
        batch_id = avl_list[0]["batch_id"]
        validate_avl_list(avl_list, batch_id)
        try:
            to_set, to_remove, stop_history = positions_timetable_lookup(
                timetable_store,
                avl_list,
                stop_history,
            )
            db_client.historic_update_success(
                batch_id,
                to_set,
                to_remove,
                date_str,
            )
        except Exception:
            logger.exception("An error occurred when processing historic record")
            db_client.batch_failed(batch_id)


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
        local_timetable_path = "/tmp/timetable.parquet"
        local_avl_path = "/tmp/avl.parquet"
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
