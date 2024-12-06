import polars as pl


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
    ) -> tuple[str, dict]:
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
        group_timetable_with_direction = group_timetable.group_by(
            "direction",
            maintain_order=True,
        ).all()
        direction_count = (
            group_timetable_with_direction.select(pl.len()).collect().item()
        )
        if direction_count > 1:
            group_id = group_id + "|" + direction_ref
            group_timetable = group_timetable_with_direction.filter(
                pl.col("direction") == direction_ref,
            )
        else:
            group_timetable = group_timetable.group_by(
                "group_id",
                maintain_order=True,
            ).all()
        row_count = group_timetable.select(pl.len()).collect().item()
        grouped_dict = {}
        for i in range(row_count):
            row = (
                group_timetable.filter(pl.int_range(pl.len()).is_in([i]))
                .collect()
                .row(0, named=True)
            )
            for stop in range(1, len(row["stop_index"]) + 1):
                grouped_dict.setdefault(group_id, {})[str(stop)] = (
                    (
                        float(row["stop_latitude"][stop - 1]),
                        float(row["stop_longitude"][stop - 1]),
                    ),
                    row["expected_departure_time"][stop - 1],
                    row["timetable_id"][stop - 1],
                    row["date_of_journey"][stop - 1],
                )
        return group_id, grouped_dict[group_id]
