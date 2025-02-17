"""Fetching and Uploading Data into S3"""

import hashlib
import json
import os
from collections.abc import Iterable, Sequence
from typing import Any

import boto3
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.streaming.s3_object import S3Object
from aws_lambda_powertools.utilities.streaming.transformations import (
    CsvTransform,
    GzipTransform,
)
from botocore.exceptions import ClientError

from .matcher.models import (
    LiveAVLRecord,
    StopHistory,
    Timetable,
)
from .matcher.utils import timer
from .shards import shards

logger = Logger()
shard_lookup: dict[str, str] = {}
for shard, operators in shards.items():
    for operator in operators:
        shard_lookup[operator] = shard


def to_str_or_empty(obj: Any) -> str:  # noqa:ANN401 - sometimes any is valid
    if not obj:
        return ""
    return str(obj)


# Live avl files contain more records than we need, and the ordering is important so defined here to be explicit
live_avl_column_parsers = {
    "recorded_at_time": str,
    "response_timestamp": str,
    "latitude": float,
    "longitude": float,
    "line_name": to_str_or_empty,
    "operator_ref": str,
    "vehicle_ref": str,
    "journey_ref": str,
    "direction_ref": to_str_or_empty,
    "date_of_journey": str,
    "batch_id": int,
}
avl_file_transforms = [
    GzipTransform(),
    CsvTransform(fieldnames=list(live_avl_column_parsers)),
]
def parse_live_avl_row(row: dict[str, str]):
    return {
        key: live_avl_column_parsers[key](row[key])
        for key in live_avl_column_parsers
    }


def _filter_avl_list(
    shard_no: str,
    avl_list: Iterable[LiveAVLRecord],
) -> Iterable[LiveAVLRecord]:
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
            size = round(len(content) / 1024, 2)
            logger.info(
                "Successfully fetched data from S3",
                s3_key=key,
                size_kb=size,
            )
            return json.loads(content)
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            logger.exception(
                "Failed to fetch data from S3",
                s3_key=key,
                error_code=error_code,
            )
            raise

    def get_timetable_extract(self) -> Timetable:
        """Download Main Timetable Data"""
        return self._get_from_s3("timetable/timetable.json")

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
        else:
            if "control_info" in stop_history:
                del stop_history["control_info"]

            logger.info(
                "Fetched and Parsed Stop History",
                group_ids_count=len(stop_history.keys()),
            )

            return stop_history

    @timer(logger)
    def get_avl_data(self, filename: str, shard_no: str) -> Sequence[LiveAVLRecord]:
        """Get AVL Data from S3 and return a list of AVLData models for the current shard"""
        avl_stream = self._get_all_avl_data(filename)
        return list(_filter_avl_list(shard_no, avl_stream))

    def _get_all_avl_data(self, filename: str) -> Iterable[LiveAVLRecord]:
        logger.info("Getting AVL Data", path=filename)
        obj = S3Object(bucket=self.bucket, key=filename, boto3_client=self.client)
        for row in obj.transform(avl_file_transforms):
            yield parse_live_avl_row(row)

    @timer(logger)
    def export_stop_history(self, stop_history: StopHistory, shard_no: str) -> None:
        """Export JourneyStopHistory data to S3"""
        s3_key = stop_history_key(shard_no)
        logger.info(
            "Storing Stop history",
            s3_key=s3_key,
            group_id_count=len(stop_history.keys()),
        )
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=s3_key,
                Body=json.dumps(stop_history, default=str),
            )
            logger.info("S3 upload successful", path=s3_key)
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            logger.exception(
                "S3 upload failed",
                path=s3_key,
                error_code=error_code,
            )
            raise


def stop_history_key(shard_no: str) -> str:
    return f"stop_history/live/shard_{shard_no}.json"
