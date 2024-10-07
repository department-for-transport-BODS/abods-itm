from datetime import datetime
from typing import Optional

from .utils import validate_date


class AVLRecord:
    def __init__(self, data):
        self._data = data

    @property
    def group_id(self):
        return f"{self.operator_ref}{self.line_name}{self.journey_ref}{self.date_of_journey}"

    @property
    def date_of_journey(self):
        return str(self._data["date_of_journey"])

    @property
    def journey_ref(self):
        return self._data["journey_ref"]

    @property
    def operator_ref(self):
        return self._data["operator_ref"]

    @property
    def line_name(self):
        return self._data["line_name"]

    @property
    def latitude(self):
        return float(self._data["latitude"])

    @property
    def longitude(self):
        return float(self._data["longitude"])

    @property
    def recorded_at_time_utc(self) -> Optional[datetime]:
        return validate_date(self._data["recorded_at_time"][:19])

    @property
    def recorded_at_time_utc_str(self):
        return datetime.strftime(self.recorded_at_time_utc, "%Y-%m-%dT%H:%M:%S")
