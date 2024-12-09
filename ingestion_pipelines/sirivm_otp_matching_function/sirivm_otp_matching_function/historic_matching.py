# This file is the entry point of an ECS task that performs a long-lived matching process.
# It lives alongside the lambda code for ease of development

import json
import os
import sys
from datetime import datetime
from pathlib import Path

import boto3
import polars as pl
from aws_lambda_powertools import Logger
from dateutil.parser import parse

from .client_db import TimetableDBClient
from .matcher.handle_stop_history import clean_stop_history
from .matcher.historic_timetable_store import HistoricTimetableStore
from .matcher.matching import positions_timetable_lookup
from .matcher.models import (
    ControlInfo,
    StopHistory,
)
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
def write_to_json(data: dict, output_path: Path) -> None:
    """
    Write data to json

    Args:
    ----
        data (dict): data in dict type
        output_path (str): The destination path

    """
    output_path.parent.mkdir(exist_ok=True, parents=True)
    with open(output_path, "w+") as f:
        f.write(json.dumps(data))


@timer(logger)
def get_stop_history(
    query_date: str,
) -> StopHistory:
    """Get Stop History"""
    path = (
        Path(__file__).parent.parent
        / "historic_data"
        / "timetable_avl"
        / query_date
        / "timetable_avl_stop_history.json"
    )

    if not path.is_file():
        logger.info("Stop history file does not exist")
        return {}

    with open(path) as f:
        stop_history = json.load(f)
    del stop_history["control_info"]

    return stop_history


@timer(logger)
def validate_avl_list(
    avl_list: pl.LazyFrame,
    expected_batch_id: int,
) -> None:
    if (
        avl_list.filter(pl.col("batch_id") != expected_batch_id)
        .select(pl.len())
        .collect()
        .item()
        > 0
    ):
        raise Exception("AVLs with multiple match ids retrieved")  # noqa: TRY002 - Not worth making an exception type


def new_control_info(avl_time: int) -> ControlInfo:
    return {
        "last_avl": avl_time,
        "last_avl_processed_time": str(datetime.now()),
    }


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
    stop_history = get_stop_history(date_str)

    avl_data = read_parquet_s3(avl_path)
    logger.info(f"Loaded avl data for {date_str}")

    avl_group_count = (
        avl_data.group_by("response_time_stamp", maintain_order=True).len().collect()
    )
    avl_response_time_list = avl_group_count.get_column("response_time_stamp")
    cleaned_stop_history = stop_history

    for rt in avl_response_time_list:
        logger.info(f"Run historic matching for batch at {rt}")
        if len(stop_history) > 1:
            cleaned_stop_history = clean_stop_history(stop_history, parse(rt))
        avl_rt = avl_data.filter(pl.col("response_time_stamp") == rt)
        avl_row_count = (
            avl_data.filter(pl.col("response_time_stamp") == rt)
            .select(pl.len())
            .collect()
            .item()
        )
        avl_list = [
            avl_rt.filter(pl.int_range(pl.len()).is_in([i]))
            .collect()
            .row(0, named=True)
            for i in range(avl_row_count)
        ]
        batch_id = avl_list[0]["batch_id"]
        try:
            control_info = new_control_info(rt)
            to_set, to_remove, stop_history = positions_timetable_lookup(
                HistoricTimetableStore(timetable),
                avl_list,
                cleaned_stop_history,
            )
            write_to_json(
                {**stop_history, "control_info": control_info},
                Path(__file__).parent.parent
                / "historic_data"
                / "timetable_avl"
                / date_str
                / "timetable_avl_stop_history.json",
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
