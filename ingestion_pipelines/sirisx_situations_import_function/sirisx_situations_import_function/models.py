from dataclasses import dataclass
from datetime import date, datetime


@dataclass
class SituationRecord:
    producer_ref: str
    situation_number: str
    version: str | None
    operator_noc: str | None
    line_name: str | None
    direction: str | None
    date_of_journey: date
    origin_departure_time: datetime
    validity_start_date: datetime | None
    validity_end_date: datetime | None
    journey_code: str | None
    condition: str | None
    progress: str | None
    event_timestamp: datetime
    creation_time: datetime

    def to_dict(self) -> dict:
        return self.__dict__
