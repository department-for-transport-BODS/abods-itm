from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Literal, TypedDict

from .utils import validate_date

StopDetails = tuple[tuple[float, float], str, int, str]
RouteDetails = Mapping[str, StopDetails]
Timetable = Mapping[str, RouteDetails]
OperatorShards = Mapping[str, Sequence[str]]


def stop_latitude(stop: StopDetails) -> float:
    return stop[0][0]


def stop_longitude(stop: StopDetails) -> float:
    return stop[0][1]


def stop_expected_time(stop: StopDetails) -> str:
    return stop[1]


def stop_timetable_id(stop: StopDetails) -> int:
    return stop[2]


def stop_date(stop: StopDetails) -> str:
    return stop[3]


def stop_departure_time(stop: StopDetails) -> datetime:
    """Datetime of the expected stop departure"""
    return validate_date(f"{stop_date(stop)} {stop_expected_time(stop)}")


class AVLRecord(TypedDict):
    """AVL record"""

    recorded_at_time: str
    response_timestamp: str
    latitude: float
    longitude: float
    line_name: str
    operator_ref: str
    vehicle_ref: str
    journey_ref: str
    direction_ref: str
    date_of_journey: str
    batch_id: int


avl_data_type = AVLRecord.__annotations__


def avl_group_id(avl: AVLRecord) -> str:
    return f'{avl["operator_ref"]}|{avl["line_name"]}|{avl["journey_ref"]}|{avl["date_of_journey"]}'.lower()


def avl_recorded_at_time_utc(avl: AVLRecord) -> datetime:
    return validate_date(avl["recorded_at_time"][:19])


class RecordToRemove(TypedDict):
    """Represents a record to be removed from the DB after matching"""

    timetable_id: int
    group_id: str


class RecordToAdd(TypedDict):
    """Represents a record to be added to the DB after matching"""

    stop_index: str
    group_id: str
    time_difference: float
    last_time_in_zone_str: str
    timetable_id: int
    batch_id: int
    last_time_in_zone: datetime
    otp_state: Literal["Early", "OnTime", "Late"]
    stop_type: Literal["final", "Non-final"]
