"""Fetching and Uploading Data into S3"""

import json
import os
import time
from collections.abc import Sequence
from datetime import datetime
from typing import Any

import awswrangler as wr
import boto3
from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError
from pandas import DataFrame

from .matcher.models import (
    ControlInfo,
    LiveAVLRecord,
    OperatorShards,
    StopHistory,
    Timetable,
    live_avl_file_columns,
)
from .matcher.utils import timer

logger = Logger()
client = boto3.client("s3")


def filter_avl_list(
    shard_identifier: str,
    sharded_operators: OperatorShards,
    avl_list: Sequence[LiveAVLRecord],
) -> Sequence[LiveAVLRecord]:
    """Given a list of AVLs, returns an AVL list filtered to operators just for this particular shard id"""
    if shard_identifier == "0":
        # Allow all operators that aren't in a shard
        all_sharded_operators = [
            x for id_no, operators in sharded_operators.items() for x in operators
        ]
        return [
            avl for avl in avl_list if avl["operator_ref"] not in all_sharded_operators
        ]

    return [
        avl
        for avl in avl_list
        if avl["operator_ref"] in sharded_operators.get(shard_identifier, [])
    ]


def _new_control_info(avl_time: int) -> ControlInfo:
    return {
        "last_avl": avl_time,
        "last_avl_processed_time": str(datetime.now()),
    }


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
        return self.download_timetable("timetable/timetable.json")

    @timer(logger)
    def download_timetable(self, key: str) -> Timetable:
        """Download Timetable Data"""
        return self._get_from_s3(key)

    @timer(logger)
    def get_shards(self) -> OperatorShards:
        """Get Shard Data from S3 and return Shards Model"""
        return self._get_from_s3("shards.json")["shards"]

    @timer(logger)
    def get_stop_history(
        self,
        query_date: datetime,
        shard_no: str,
        avl_time: int,
    ) -> tuple[StopHistory, ControlInfo]:
        """Get Stop History"""
        date_str = query_date.strftime("%Y-%m-%d")
        key = (
            f"timetable_avl/{date_str}/timetable_avl_stop_history_shard{shard_no}.json"
        )
        logger.info("Fetching Stop History", s3_key=key)
        try:
            stop_history = self._get_from_s3(key)
        except ClientError as ex:
            if ex.response.get("Error", {}).get("Code", None) == "NoSuchKey":
                logger.info("Stop History Not Found, Returning Empty Dict", key=key)
                return {}, _new_control_info(avl_time)
            raise
        logger.info(
            "Fetched and Parsed Stop History",
            group_ids_count=len(stop_history.keys()),
        )

        if "control_info" not in stop_history:
            return stop_history, _new_control_info(avl_time)

        control_info: ControlInfo = stop_history["control_info"]
        del stop_history["control_info"]

        last_file = control_info["last_avl"]
        last_time = control_info.get(
            "last_avl_processed_time",
            "No record",
        )
        if int(last_file) > avl_time:
            logger.warning(
                f"AVL is not in order, last avl: {last_file}, current avl: {avl_time}",
            )
        elif int(last_file) == avl_time:
            logger.warning(
                f"Same AVL data coming in, last avl processed time: {last_time}, current last avl: {last_file}, current avl: {avl_time}",
            )
        return stop_history, _new_control_info(avl_time)

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
    def export_stop_history(
        self,
        stop_history: StopHistory,
        control_info: ControlInfo,
        current_date: datetime,
        shard_no: str,
    ) -> None:
        """Export JourneyStopHistory data to S3"""
        date_str = current_date.strftime("%Y-%m-%d")
        s3_key = (
            f"timetable_avl/{date_str}/timetable_avl_stop_history_shard{shard_no}.json"
        )
        logger.info(
            "S3 Upload: Storing Stop history",
            s3_key=s3_key,
            group_id_count=len(stop_history.keys()),
        )
        self._write_to_s3(
            {**stop_history, "control_info": control_info},
            s3_key,
        )
