import polars as pl

from .models import RouteDetails, StopDetails


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
        group_timetable = self._timetable.filter(pl.col("group_id") == group_id)
        timetable = (
            group_timetable.with_columns(
                "direction",
                "stop_index",
                "stop_latitude",
                "stop_longitude",
                "expected_departure_time",
                "timetable_id",
                "date_of_journey",
            )
            .collect()
            .to_dicts()
        )
        journey_index = group_id + "|" + direction_ref

        if not timetable:
            return journey_index, None

        directions = {rec["direction"] for rec in timetable}
        if len(directions) <= 1:
            journey_index = group_id
        else:
            timetable = [rec for rec in timetable if rec["direction"] == direction_ref]

        if not timetable:
            return journey_index, None

        timetable.sort(key=lambda rec: int(rec["stop_index"]))
        converted_timetable: dict[str, StopDetails] = {}
        for index, row in enumerate(timetable):
            converted_timetable[str(index + 1)] = (
                (
                    float(row["stop_latitude"]),
                    float(row["stop_longitude"]),
                ),
                (row["expected_departure_time"]),
                int(row["timetable_id"]),
                (row["date_of_journey"]),
            )
        return journey_index, converted_timetable
