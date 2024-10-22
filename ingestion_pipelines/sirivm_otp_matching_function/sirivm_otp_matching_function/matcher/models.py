from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Literal, TypedDict

from attr import dataclass

from .utils import validate_date


@dataclass
class StopDetails:
    """Represents a stop within a timetabled route"""

    latitude: float
    longitude: float
    expected_time: str
    timetable_id: int
    date: str

    @property
    def timetable_departure_time(self) -> datetime:
        """Datetime of the expected stop departure"""
        return validate_date(f"{self.date} {self.expected_time}")


RouteDetails = Mapping[str, StopDetails]
Timetable = Mapping[str, RouteDetails]
OperatorShards = Mapping[str, Sequence[str]]


class AVLRecord:
    """Wrapper class with convenience methods for an AVL"""

    def __init__(self, data: Mapping) -> None:
        """Construct an AVL record given a dict record from a CSV"""
        self._data = data

    @property
    def group_id(self) -> str:
        """The group_id of the avl record with | as separator"""
        return f"{self.operator_ref}|{self.line_name}|{self.journey_ref}|{self.date_of_journey}".lower()

    @property
    def date_of_journey(self) -> str:
        """The date of the journey for this avl"""
        return str(self._data["date_of_journey"])

    @property
    def journey_ref(self) -> str:
        """The journey reference of the avl"""
        return self._data["journey_ref"]

    @property
    def operator_ref(self) -> str:
        """The operator reference of the avl"""
        return self._data["operator_ref"]

    @property
    def line_name(self) -> str:
        """The line name of the avl"""
        return self._data["line_name"]

    @property
    def latitude(self) -> float:
        """The latitude of the avl"""
        return float(self._data["latitude"])

    @property
    def longitude(self) -> float:
        """The longitude of the avl"""
        return float(self._data["longitude"])

    @property
    def recorded_at_time_utc(self) -> datetime:
        """The recorded at time"""
        return validate_date(self._data["recorded_at_time"][:19])

    @property
    def recorded_at_time_utc_str(self) -> str:
        """The recorded at time as a string"""
        return datetime.strftime(self.recorded_at_time_utc, "%Y-%m-%dT%H:%M:%S")

    @property
    def batch_id(self) -> int:
        """The batch_id"""
        return self._data["batch_id"]


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
