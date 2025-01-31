"""Fetching and Uploading Data into S3"""

import hashlib
import json
import os
import time
from collections.abc import Generator, Sequence
from typing import Any

import awswrangler as wr
import boto3
from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError
from pandas import DataFrame

from .matcher.models import (
    LiveAVLRecord,
    OperatorShards,
    StopHistory,
    Timetable,
    live_avl_file_columns,
)
from .matcher.utils import timer
from .shards import shards

logger = Logger()
client = boto3.client("s3")
shard_lookup: dict[str, str] = {}
for shard, operators in shards.items():
    for operator in operators:
        shard_lookup[operator] = shard


def filter_avl_list(
    shard_no: str,
    avl_list: Sequence[LiveAVLRecord],
) -> Generator[LiveAVLRecord]:
    """Given a list of AVLs, returns an AVL list filtered to operators just for this particular shard id"""
    for avl in avl_list:
        operator_ref = avl["operator_ref"]
        if operator_ref not in shard_lookup:
            # Hashing to consistently pick a shard, not for security
            hashed = hashlib.sha224(operator_ref.encode("utf-8")).hexdigest()
            shard_lookup[operator_ref] = str(int(hashed, 16) % len(shards))

        if shard_lookup[operator_ref] != shard_no:
            continue

        yield avl


class TimetableS3Client:
    """Download / Upload Data from S3 with Parsing"""

    def __init__(self) -> None:
        """Construct a client"""
        self.client = boto3.client("s3")
        self.bucket = os.environ["SIRIVM_BUCKET"]
        logger.append_keys(s3_bucket=self.bucket)

    def _get_from_s3(self, key: str) -> Any:  # noqa: ANN401 - Any is correct here, callers should determine actual type
        """Get data from S3"""
        try:
            logger.info("Fetching data from S3", s3_key=key)
            content = (
                self.client.get_object(Bucket=self.bucket, Key=key).get("Body").read()
            )
            size = round(len(content) / (1024), 2)
            logger.info(
                "Successfully fetched data from S3",
                s3_key=key,
                size_kb=size,
            )
            return json.loads(content)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.exception(
                "Failed to fetch data from S3",
                s3_key=key,
                error_code=error_code,
            )
            raise

    def _write_to_s3(self, data_dict: dict[str, Any], path: str) -> None:
        """Write dict as JSON file to S3"""
        try:
            data_string = json.dumps(data_dict, default=str)
            self.client.put_object(Bucket=self.bucket, Key=path, Body=data_string)
            logger.info("S3 upload successful", path=path)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.exception(
                "S3 upload failed",
                path=path,
                error_code=error_code,
            )
            raise

    def download_main_timetable(self) -> Timetable:
        """Download Main Timetable Data"""
        return self._get_from_s3("timetable/timetable.json")

    @timer(logger)
    def get_shards(self) -> OperatorShards:
        """Get Shard Data from S3 and return Shards Model"""
        return self._get_from_s3("shards.json")["shards"]

    @timer(logger)
    def get_stop_history(self, shard_no: str) -> StopHistory:
        """Get Stop History"""
        key = stop_history_key(shard_no)
        logger.info("Fetching Stop History", s3_key=key)
        try:
            stop_history = self._get_from_s3(key)
        except ClientError as ex:
            if ex.response.get("Error", {}).get("Code", None) == "NoSuchKey":
                logger.info("Stop History Not Found, Returning Empty Dict", key=key)
                return {}
            raise
        logger.info(
            "Fetched and Parsed Stop History",
            group_ids_count=len(stop_history.keys()),
        )

        if "control_info" in stop_history:
            del stop_history["control_info"]

        return stop_history

    def get_avl_data_df(self, filename: str | list[str]) -> DataFrame:
        """Get AVL Data Dataframe"""
        paths: list[str] = []
        if isinstance(filename, list):
            paths = [f"s3://{self.bucket}/{path}" for path in filename]
        else:
            paths = [f"s3://{self.bucket}/{filename}"]
        logger.info("Getting AVL Data", path=filename)
        logger.info(
            "Fetching AVL Data can take a while...",
            number_of_files=len(filename),
        )
        start_time = time.time()
        keys = list(live_avl_file_columns.keys())
        data = wr.s3.read_csv(
            path=paths,
            use_threads=True,
            names=keys,
            dtype=live_avl_file_columns,
            usecols=keys,
            header=None,
        )
        data["line_name"] = data["line_name"].fillna("")
        data["direction_ref"] = data["direction_ref"].fillna("")
        logger.info(
            "AVL Downloaded and Parsed into DataFrame",
            count=len(data),
            processing_time=time.time() - start_time,
        )
        return data

    @timer(logger)
    def get_avl_data(self, filename: str | list[str]) -> Sequence[LiveAVLRecord]:
        """Get AVL Data from S3 and return a list of AVLData models"""
        data = self.get_avl_data_df(filename)
        return data.to_dict("records")

    @timer(logger)
    def export_stop_history(self, stop_history: StopHistory, shard_no: str) -> None:
        """Export JourneyStopHistory data to S3"""
        s3_key = stop_history_key(shard_no)
        logger.info(
            "S3 Upload: Storing Stop history",
            s3_key=s3_key,
            group_id_count=len(stop_history.keys()),
        )
        self._write_to_s3(
            stop_history,
            s3_key,
        )


def stop_history_key(shard_no: str) -> str:
    return f"stop_history/live/shard_{shard_no}.json"
