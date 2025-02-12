"""Fetching and Uploading Data into S3"""

import codecs
import csv
import gzip
import hashlib
import json
import os
from collections.abc import Iterable, Sequence

import boto3
from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError
from botocore.response import StreamingBody

from .matcher.models import (
    LiveAVLRecord,
    StopHistory,
    Timetable,
    live_avl_column_parsers,
)
from .matcher.utils import timer
from .shards import shards

logger = Logger()
utf8_stream_reader = codecs.getreader("utf-8")
avl_keys = list(live_avl_column_parsers.keys())
avl_parsers = [live_avl_column_parsers[key] for key in avl_keys]
shard_lookup: dict[str, str] = {}
for shard, operators in shards.items():
    for operator in operators:
        shard_lookup[operator] = shard


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

    def _get_from_s3(self, key: str) -> StreamingBody:
        """Get streaming data from S3"""
        try:
            logger.info("Fetching data from S3", s3_key=key)
            return self.client.get_object(Bucket=self.bucket, Key=key)["Body"]
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            logger.exception(
                "Failed to fetch data from S3",
                s3_key=key,
                error_code=error_code,
            )
            raise

    def download_main_timetable(self) -> Timetable:
        """Download Main Timetable Data"""
        return json.load(self._get_from_s3("timetable/timetable.json"))

    @timer(logger)
    def get_stop_history(self, shard_no: str) -> StopHistory:
        """Get Stop History"""
        s3_key = stop_history_key(shard_no)
        logger.info("Fetching Stop History", s3_key=s3_key)
        try:
            stop_history = json.load(self._get_from_s3(s3_key))
        except ClientError as ex:
            if ex.response.get("Error", {}).get("Code", None) == "NoSuchKey":
                logger.info("Stop History Not Found, Returning Empty Dict", key=s3_key)
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
        s3_data_stream = self._get_from_s3(filename)
        with (
            gzip.GzipFile(fileobj=s3_data_stream) as uncompressed_stream,
            utf8_stream_reader(uncompressed_stream) as decoded_stream,
        ):
            reader = csv.reader(decoded_stream)
            for row in reader:
                avl_record: LiveAVLRecord = {
                    key: parser(row[idx])
                    for idx, (key, parser) in enumerate(
                        zip(avl_keys, avl_parsers, strict=True),
                    )
                }
                yield avl_record

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
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.exception(
                "S3 upload failed",
                path=s3_key,
                error_code=error_code,
            )
            raise


def stop_history_key(shard_no: str) -> str:
    return f"stop_history/live/shard_{shard_no}.json"
