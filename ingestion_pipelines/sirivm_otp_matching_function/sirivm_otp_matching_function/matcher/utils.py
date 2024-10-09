import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal, ParamSpec, TypeVar

import boto3
from aws_lambda_powertools import Logger

EARLY_THRESHOLD_IN_SECONDS = 60
LATE_THRESHOLD_IN_SECONDS = 359


logger = Logger()
session = boto3.Session()

Param = ParamSpec("Param")
Return = TypeVar("Return")


def timer(passed_logger: Logger) -> Callable[Param, Return]:
    def decorate(f: Callable[Param, Return]) -> Callable[Param, Return]:
        def applicator(*args: Param, **kwargs: Param) -> Return:
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
    """
    Validate the date

    Args:
        date_input (datetime | str): Date input

    Returns:
        datetime: Converted datetime

    """
    if isinstance(date_input, datetime):
        return date_input
    date_input_wo_tz = date_input[:19]

    date_format = "%Y-%m-%d %H:%M:%S"
    if "T" in date_input:
        date_format = "%Y-%m-%dT%H:%M:%S"

    return datetime.strptime(date_input_wo_tz, date_format).replace(tzinfo=UTC)


def get_time_difference(
    last_time_in_zone: datetime,
    timetable_departure_time: datetime,
) -> float:
    """
    Calculate the time difference between the last time in zone and the expected departure time

    Args:
        last_time_in_zone (datetime): Last time in zone
        timetable_departure_time (datetime): Expected departure time

    Returns:
        float: The time difference between the last time in zone and the expected departure time

    """
    hour = 3600
    time_difference = (last_time_in_zone - timetable_departure_time).total_seconds()
    if time_difference < -(hour * 2) or time_difference > hour:
        logger.warning(
            f"time difference: {time_difference}, last_time_in_zone: {last_time_in_zone}, timetable_departure_time {validate_date(timetable_departure_time)}",
        )
    return time_difference


def get_otp_state(
    is_final_stop: bool,  # noqa: FBT001 - Can be split up later
    time_difference: float,
) -> Literal["Early", "OnTime", "Late"]:
    """Calculate the otp state based on seconds of time difference"""
    if not is_final_stop and time_difference < -EARLY_THRESHOLD_IN_SECONDS:
        return "Early"

    if time_difference > LATE_THRESHOLD_IN_SECONDS:
        return "Late"

    return "OnTime"
