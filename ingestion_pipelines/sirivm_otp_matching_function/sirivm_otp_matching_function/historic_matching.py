# This file is the entry point of an ECS task that performs a long-lived matching process.
# It lives alongside the lambda code for ease of development

import os
import sys
from collections.abc import Sequence

import boto3
import polars as pl
from aws_lambda_powertools import Logger
from dateutil.parser import parse

from .client_db import TimetableDBClient
from .matcher.handle_stop_history import clean_stop_history
from .matcher.historic_timetable_store import HistoricTimetableStore
from .matcher.matching import positions_timetable_lookup
from .matcher.models import AVLRecord
from .matcher.utils import timer

logger = Logger()
db_client = TimetableDBClient()

two_hours_secs = -7200

session = boto3.session.Session()
credentials = session.get_credentials().get_frozen_credentials()


def read_parquet_s3(source: str) -> pl.LazyFrame:
    """
    Read parquet file from s3

    Args:
    ----
        source (str): The source path of the parquet file

    Returns:
    -------
        pl.LazyFrame

    """
    return pl.scan_parquet(
        source,
        storage_options={
            "aws_access_key_id": credentials.access_key,
            "aws_secret_access_key": credentials.secret_key,
            "aws_session_token": credentials.token,
            "aws_region": session.region_name,
        },
    )


@timer(logger)
def validate_avl_list(
    avl_list: Sequence[AVLRecord],
    expected_batch_id: int,
) -> None:
    for avl in avl_list:
        if avl["batch_id"] != expected_batch_id:
            raise Exception("AVLs with multiple match ids retrieved")  # noqa: TRY002 - Not worth making an exception type


@timer(logger)
def historic_matching(avl_path: str, timetable: pl.LazyFrame, date_str: str) -> None:
    """
    Run historic matching

    Args:
    ----
        avl_path (str): Path to avl parquet
        timetable (pl.LazyFrame): Path to timetable parquet
        date_str (str): The date for historic matching

    """
    avl_data = read_parquet_s3(avl_path)
    logger.info(f"Loaded avl data for {date_str}")
    avl_group = avl_data.group_by("response_time_stamp", maintain_order=True)
    avl_group_count = avl_group.len().collect()
    avl_response_time_list = avl_group_count.get_column("response_time_stamp")

    stop_history = {}
    for rt in avl_response_time_list:
        logger.info(f"Run historic matching for batch at {rt}")
        if len(stop_history) > 1:
            stop_history = clean_stop_history(stop_history, parse(rt))
        avl_batch = (
            avl_group.all()
            .filter(pl.col("response_time_stamp") == rt)
            .collect()
            .row(0, named=True)
        )
        avl_list = []
        for index, _avl_id in enumerate(avl_batch["siri_vm_positions_id"]):
            avl: AVLRecord = {
                "recorded_at_time": str(avl_batch["recorded_at_time"][index]),
                "response_timestamp": str(avl_batch["response_time_stamp"]),
                "latitude": float(avl_batch["latitude"][index]),
                "longitude": float(avl_batch["longitude"][index]),
                "line_name": str(avl_batch["line_name"][index]),
                "operator_ref": str(avl_batch["operator_ref"][index]),
                "vehicle_ref": str(avl_batch["vehicle_ref"][index]),
                "journey_ref": str(avl_batch["journey_ref"][index]),
                "direction_ref": str(avl_batch["direction_ref"][index]),
                "date_of_journey": str(avl_batch["date_of_journey"][index]),
                "batch_id": int(avl_batch["batch_id"][index]),
            }
            avl_list.append(avl)
        batch_id = avl_batch["batch_id"][0]
        validate_avl_list(avl_list, batch_id)
        try:
            to_set, to_remove, stop_history = positions_timetable_lookup(
                HistoricTimetableStore(timetable),
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
    timetable_path = f"s3://{s3_bucket}/historic/parquet/YYYY={year}/MM={month}/DD={day}/timetable_{year}{month}{day}.parquet"
    timetable_lf = read_parquet_s3(timetable_path)
    logger.info(f"Loaded timetable for {process_date}")
    historic_matching(
        avl_path=f"s3://{s3_bucket}/historic/parquet/YYYY={year}/MM={month}/DD={day}/siri_vm_{year}{month}{day}.parquet",
        timetable=timetable_lf,
        date_str=process_date,
    )
