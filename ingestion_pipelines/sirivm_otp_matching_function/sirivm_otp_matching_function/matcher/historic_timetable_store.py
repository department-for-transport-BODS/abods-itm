import polars as pl
from aws_lambda_powertools import Logger

from .models import RouteDetails, StopDetails
from .utils import timer

logger = Logger()


class HistoricTimetableStore:
    """Timetable store for historic matching"""

    def __init__(self, timetable: pl.LazyFrame) -> None:
        """
        Initiate historic timetable store

        Args:
        ----
            timetable (pl.LazyFrame): The timetable for matching

        """
        self._timetable = timetable

    @timer(logger)
    def get_route_details(
        self,
        group_id: str,
        direction_ref: str,
    ) -> tuple[str, RouteDetails | None]:
        """
        Get route details

        Args:
        ----
            group_id (str): group_id for getting the route details
            direction_ref (str): The avl direction ref

        Returns:
        -------
            tuple[str, RouteDetails]: group_id and route details

        """
        group_timetable = self._timetable.group_by(pl.col("group_id"))
        filtered_timetable_df = group_timetable.all().filter(
            pl.col("group_id") == group_id,
        )
        route_details: dict[str, StopDetails] = {}
        if filtered_timetable_df.select(pl.len()).collect().item() > 0:
            journey_timetable = filtered_timetable_df.collect().row(0, named=True)
            for stop in range(len(journey_timetable["stop_index"])):
                route_details[str(stop + 1)] = (
                    (
                        float(journey_timetable["stop_latitude"][stop]),
                        float(journey_timetable["stop_longitude"][stop]),
                    ),
                    journey_timetable["expected_departure_time"][stop],
                    int(journey_timetable["timetable_id"][stop]),
                    (journey_timetable["date_of_journey"][stop]),
                )
        journey_index = group_id + "|" + direction_ref
        if not route_details:
            return journey_index, None

        directions = set(journey_timetable["direction"])
        timetable: dict[str, StopDetails] = {}
        if len(directions) <= 1:
            journey_index = group_id
            timetable = route_details
        else:
            index = 0
            for ind, direction in enumerate(journey_timetable["direction"]):
                if direction == direction_ref:
                    index += 1
                    timetable[str(index)] = route_details[str(ind + 1)]

        if not timetable:
            return journey_index, None

        timetable = dict(sorted(timetable.items(), key=lambda x: x[0]))
        return journey_index, timetable
