import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal, ParamSpec, TypeVar

import boto3
import pyproj
from aws_lambda_powertools import Logger
from shapely import LineString, MultiLineString, Point

EARLY_THRESHOLD_IN_SECONDS = 60
LATE_THRESHOLD_IN_SECONDS = 359


logger = Logger()
session = boto3.Session()

Param = ParamSpec("Param")
Return = TypeVar("Return")

source_crs = pyproj.CRS("EPSG:4326")
target_crs = pyproj.CRS("EPSG:27700")

crs_transformer = pyproj.Transformer.from_crs(source_crs, target_crs, always_xy=True)


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


def create_point(longitude: float, latitude: float) -> Point:
    """Transform coordinates to a Point."""
    return Point(crs_transformer.transform(longitude, latitude))


def create_line_string(point_a: Point, point_b: Point) -> LineString:
    """Create a line between 2 points"""
    return LineString([point_a, point_b])


def create_boundary(
    centre_longitude: float,
    centre_latitude: float,
    radius: int,
) -> MultiLineString:
    """Create a bounding circle around a point."""
    circle_centre = create_point(centre_longitude, centre_latitude)

    return circle_centre.buffer(radius).boundary
