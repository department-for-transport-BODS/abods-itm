"""Fetching and Uploading Data into S3"""

import json
import os
import time
from datetime import datetime
from typing import Any

import awswrangler as wr
import boto3
from aws_lambda_powertools import Logger
from botocore.exceptions import ClientError
from pandas import DataFrame

from .matcher.models import AVLRecord, RouteDetails, StopDetails
from .matcher.utils import timer

logger = Logger()
client = boto3.client("s3")


def parse_timetable(timetable: dict[str, dict[str, list]]) -> dict[str, RouteDetails]:
    parsed = {}
    for group_id, route in timetable.items():
        parsed[group_id] = {}
        for key, value in route.items():
            parsed[group_id][key] = StopDetails(
                latitude=value[0][0],
                longitude=value[0][1],
                expected_time=value[1],
                timetable_id=value[2],
                date=value[3],
            )
    return parsed


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
        data_string = json.dumps(data_dict, default=str)
        self.client.put_object(Bucket=self.bucket, Key=path, Body=data_string)
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

    @timer(logger)
    def download_main_timetable(self) -> dict[str, RouteDetails]:
        """Download Main Timetable Data"""
        return self.download_timetable("timetable/timetable.json")

    def download_timetable(self, key: str) -> dict[str, RouteDetails]:
        """Download Timetable Data"""
        data = self._get_from_s3(key)
        return parse_timetable(data)

    @timer(logger)
    def get_shards(self) -> dict:
        """Get Shard Data from S3 and return Shards Model"""
        return self._get_from_s3("shards.json")

    @timer(logger)
    def get_stop_history(
        self,
        query_date: datetime,
        shard_no: str,
        avl_timestamp: int,
    ) -> dict:
        """Get Stop History"""
        date_str = query_date.strftime("%Y-%m-%d")
        stop_history: dict = {
            "control_info": {
                "last_avl": avl_timestamp,
                "last_avl_processed_time": datetime.now(),
            },
        }
        key = (
            f"timetable_avl/{date_str}/timetable_avl_stop_history_shard{shard_no}.json"
        )
        logger.info("Fetching Stop History", s3_key=key)
        try:
            stop_history = self._get_from_s3(key)
            logger.info(
                "Fetched and Parsed Stop History",
                group_ids_count=len(stop_history.keys()),
            )
            if "control_info" in stop_history:
                last_avl_filename = stop_history["control_info"]["last_avl"]
                last_avl_processed_time = stop_history["control_info"].get(
                    "last_avl_processed_time",
                    "No record",
                )
                if int(last_avl_filename) > avl_timestamp:
                    logger.warning(
                        f"AVL is not in order, last avl: {stop_history['control_info']['last_avl']}, current avl: {avl_timestamp}",
                    )
                elif int(last_avl_filename) == avl_timestamp:
                    logger.warning(
                        f"Same AVL data coming in, last avl processed time: {last_avl_processed_time}, current last avl: {stop_history['control_info']['last_avl']}, current avl: {avl_timestamp}",
                    )
        except ClientError as ex:
            if ex.response.get("Error", {}).get("Code", None) == "NoSuchKey":
                logger.info("Stop History Not Found, Returning Empty Dict", key=key)
                return stop_history
            raise
        if "control_info" not in stop_history:
            stop_history["control_info"] = {}
        stop_history["control_info"]["last_avl"] = avl_timestamp
        stop_history["control_info"]["last_avl_processed_time"] = datetime.now()
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
        data_type = {
            "recorded_at_time": str,
            "response_timestamp": str,
            "latitude": float,
            "longitude": float,
            "line_name": str,
            "operator_ref": str,
            "vehicle_ref": str,
            "journey_ref": str,
            "direction_ref": str,
            "date_of_journey": str,
            "batch_id": int,
        }
        keys = list(data_type.keys())
        data = wr.s3.read_csv(
            path=paths,
            use_threads=True,
            names=keys,
            dtype=data_type,
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
    def get_avl_data(self, filename: str | list[str]) -> list[AVLRecord]:
        """Get AVL Data from S3 and return a list of AVLData models"""
        data = self.get_avl_data_df(filename)
        avl_list = data.to_dict("records")
        return [AVLRecord(r) for r in avl_list]

    @timer(logger)
    def export_stop_history(
        self,
        stop_history: dict[str, dict[str, Any]],
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
            stop_history,
            s3_key,
        )
