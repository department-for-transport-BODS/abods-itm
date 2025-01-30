from .models import Route, Timetable


class LiveTimetableStore:
    """Timetable store used for live matching"""

    def __init__(self, timetable: Timetable) -> None:
        """Construct a live timetable store"""
        self._timetable = timetable

    def get_route(
        self,
        group_id: str,
        direction_ref: str,
    ) -> tuple[str, Route | None]:
        """
        Get the route data for a given group id and direction

        Args:
        ----
            group_id (str): A string representing operator_ref|line_name|journey_ref|date_of_journey in lower case
            direction_ref (str): Direction ref (e.g. inbound, outbound)

        Returns:
        -------
            str: The last index used to find the route in the timetable
            Route | None: The matched route data if any

        """
        route = self._timetable.get(group_id)
        if route:
            return group_id, route

        # In some cases, there can be multiple journeys with different directions using the same group id.
        # When that happens, sirivm_timetable_s3_generation_function will add the direction ref to the group id.
        # We will also need to use this to keep track of the matching for both journeys separately,
        # but the database updates need to be with the original group id
        index = group_id + "|" + direction_ref.lower()
        return index, self._timetable.get(index)
