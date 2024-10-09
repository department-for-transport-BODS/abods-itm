import time
from datetime import datetime
from typing import Callable, Literal, ParamSpec, TypeVar

import boto3
import pytz
from aws_lambda_powertools import Logger

logger = Logger()
session = boto3.Session()
utc = pytz.utc

Param = ParamSpec("Param")
Return = TypeVar("Return")


def timer(passed_logger: Logger) -> Callable[Param, Return]:
    def decorate(f: Callable[Param, Return]):
        def applicator(*args, **kwargs):
            passed_logger.info(f"Starting {f.__name__}()")
            start_time = time.perf_counter()
            try:
                return f(*args, **kwargs)
            finally:
                end_time = time.perf_counter()
                run_time = end_time - start_time
                passed_logger.info(f"Finished {f.__name__}() in {run_time:.4f} secs")

        return applicator

    return decorate


def validate_date(date_input: datetime | str) -> datetime:
    """Validate the date

    Args:
        date_input (datetime | str): Date input

    Returns:
        datetime: Converted datetime
    """
    if isinstance(date_input, datetime):
        return date_input
    else:
        date_input_wo_tz = date_input[:19]
        if "T" in date_input:
            converted_date = datetime.strptime(date_input_wo_tz, "%Y-%m-%dT%H:%M:%S")
        else:
            converted_date = datetime.strptime(date_input_wo_tz, "%Y-%m-%d %H:%M:%S")
        return converted_date.replace(tzinfo=utc)


def get_time_difference(
    last_time_in_zone: datetime, timetable_departure_time: datetime
) -> float:
    """Calculate the time difference between the last time in zone and the expected departure time

    Args:
        last_time_in_zone (datetime): Last time in zone
        timetable_departure_time (datetime): Expected departure time

    Returns:
        float: The time difference between the last time in zone and the expected departure time
    """
    hour = 3600
    time_difference = (last_time_in_zone - timetable_departure_time).total_seconds()
    if time_difference < -(hour * 2) or time_difference > hour:
        logger.warn(
            f"time difference: {time_difference}, last_time_in_zone: {last_time_in_zone}, timetable_departure_time {validate_date(timetable_departure_time)}"
        )
    return time_difference


def get_otp_state(
    is_final_stop: bool, time_difference: float
) -> Literal["Early", "OnTime", "Late"]:
    """Calculate the otp state based on seconds of time difference"""
    if not is_final_stop and time_difference < -60:
        return "Early"

    if time_difference > 359:
        return "Late"

    return "OnTime"
