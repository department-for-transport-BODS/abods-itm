from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Literal, NotRequired, TypedDict

from .utils import validate_date

Stop = tuple[tuple[float, float], str, int, str]
Route = Mapping[str, Stop]
Timetable = Mapping[str, Route]
OperatorShards = Mapping[str, Sequence[str]]


def stop_latitude(stop: Stop) -> float:
    return stop[0][0]


def stop_longitude(stop: Stop) -> float:
    return stop[0][1]


def stop_expected_time(stop: Stop) -> str:
    return stop[1]


def stop_timetable_id(stop: Stop) -> int:
    return stop[2]


def stop_date(stop: Stop) -> str:
    return stop[3]


def stop_departure_time(stop: Stop) -> datetime:
    return validate_date(f"{stop_date(stop)} {stop_expected_time(stop)}")


class AVLRecord(TypedDict):
    recorded_at_time: str
    latitude: float
    longitude: float
    line_name: str
    operator_ref: str
    journey_ref: str
    direction_ref: str
    date_of_journey: str
    # string fields response_timestamp and vehicle_ref are also available, but not used


class LiveAVLRecord(AVLRecord):
    # Does not exist in historical data from ITO, so should not be used in new historic matching
    batch_id: int


def avl_group_id(avl: AVLRecord) -> str:
    return f"{avl['operator_ref']}|{avl['line_name']}|{avl['journey_ref']}|{avl['date_of_journey']}".lower()


def avl_recorded_at_time_utc(avl: AVLRecord) -> datetime:
    return validate_date(avl["recorded_at_time"][:19])


class BadDbMatch(TypedDict):
    """Represents a record to be removed from the DB after matching"""

    timetable_id: int


class NewDbMatch(TypedDict):
    """Represents a record to be added to the DB after matching"""

    stop_index: str
    time_difference: float
    last_time_in_zone_str: str | None
    timetable_id: int
    last_time_in_zone: datetime | None
    timestamp_after_estimate: datetime | None
    otp_state: Literal["Early", "OnTime", "Late"]
    stop_type: Literal["final", "Non-final"]


class MatchedStop(TypedDict):
    """Details of a stop that has been identified as departed on the current journey"""

    last_match_time: str
    is_estimate: bool


class PotentialMatch(TypedDict):
    """Details of a stop that could be a match upon processing a later AVL point"""

    last_distance: float
    last_time_in_zone: str
    is_estimate: NotRequired[bool]


class RouteHistory(TypedDict):
    """Stored stop details for current journey matching"""

    last_avl_time: str
    last_avl_longitude: float | None
    last_avl_latitude: float | None
    matched_stops: dict[str, MatchedStop]
    potential_matches: dict[str, PotentialMatch]


StopHistory = dict[str, RouteHistory]
