import math
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal, ParamSpec, TypeVar

import boto3
import pyproj
from aws_lambda_powertools import Logger

EARLY_THRESHOLD_IN_SECONDS = 60
LATE_THRESHOLD_IN_SECONDS = 359


logger = Logger()
session = boto3.Session()

Param = ParamSpec("Param")
Return = TypeVar("Return")

source_crs = pyproj.CRS("EPSG:4326")  # WGS 84 - World Geodetic System
target_crs = pyproj.CRS("EPSG:27700")  # British National Grid

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


def crs_transform(x: float, y: float) -> tuple[float, float]:
    return crs_transformer.transform(x, y)


def calculate_line_circle_intersection_ratios(
    circle_centre_point: tuple[float, float],
    circle_radius: float,
    line_point_1: tuple[float, float],
    line_point_2: tuple[float, float],
) -> list[float]:
    # Unpack input tuples
    h, k = circle_centre_point
    r = circle_radius
    x1, y1 = line_point_1
    x2, y2 = line_point_2

    # Calculate the line coefficients
    dx = x2 - x1
    dy = y2 - y1

    # Quadratic formula components
    a = dx**2 + dy**2
    b = 2 * (dx * (x1 - h) + dy * (y1 - k))
    c = (x1 - h) ** 2 + (y1 - k) ** 2 - r**2

    # Discriminant to check for intersections
    discriminant = b**2 - 4 * a * c

    # To store results with distances
    distances_to_intersection_ratios: list[float] = []

    if discriminant < 0:
        # No intersection
        return []

    if discriminant == 0:
        # One intersection (tangent to the circle)
        t = -b / (2 * a)
        if 0 <= t <= 1:
            return [t]

    # Two intersections
    sqrt_discriminant = math.sqrt(discriminant)

    # First intersect
    t1 = (-b - sqrt_discriminant) / (2 * a)
    if 0 <= t1 <= 1:
        distances_to_intersection_ratios.append(t1)

    # Second intersect
    t2 = (-b + sqrt_discriminant) / (2 * a)
    if 0 <= t2 <= 1:
        distances_to_intersection_ratios.append(t2)

    return distances_to_intersection_ratios
