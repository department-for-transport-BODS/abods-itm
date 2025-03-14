from datetime import date, timedelta, datetime

from .models import AVLRecord, Route, Timetable, avl_group_id, avl_recorded_at_time_utc, stop_departure_time


class LiveTimetableStore:
    """Timetable store used for live matching"""

    def __init__(self, timetable: Timetable) -> None:
        """Construct a live timetable store"""
        self._timetable = timetable

    def _get_timetable_by_index(self, timetable_index: str, avl_time:datetime) -> Route|None:
        route = self._timetable.get(timetable_index)
        if not route:
            return None

        # If the avl is more than 4 hours before the start of the journey, or more than 4 hours after the end, return nothing
        # This is mostly to help historic matching, and should never actually happen for live matching

        departure_times = [stop_departure_time(stop) for stop in route.values()]

        start_of_journey = min(departure_times)
        lower_bound = start_of_journey - timedelta(hours=4)
        if avl_time < lower_bound:
            return None

        end_of_journey = max(departure_times)
        upper_bound = end_of_journey + timedelta(hours=4)
        if avl_time > upper_bound:
            return None

        return route

    def _get_timetable_for_group_id(self, group_id: str, direction_ref:str, avl_time:datetime) -> tuple[str, Route]:
        route_details = self._get_timetable_by_index(group_id, avl_time)
        if route_details:
            return group_id, route_details

        # In some cases, there can be multiple journeys with different directions using the same group id.
        # When that happens, sirivm_timetable_s3_generation_function will add the direction ref to the group id.
        # We will also need to use this to keep track of the matching for both journeys separately,
        # but the database updates need to be with the original group id
        index = group_id + "|" + direction_ref.lower()
        route_details = self._get_timetable_by_index(index, avl_time)

        return index, route_details

    def get_route(
        self,
        avl: AVLRecord,
    ) -> tuple[str, Route | None]:
        """
        Get the route data for a given group id and direction

        Args:
        ----
            avl (AVLRecord): AVL record

        Returns:
        -------
            str: The last index used to find the route in the timetable
            Route | None: The matched route data if any

        """
        direction_ref = avl["direction_ref"]

        avl_time = avl_recorded_at_time_utc(avl)
        stop_history_index, route = self._get_timetable_for_group_id(avl_group_id(avl), direction_ref, avl_time)
        if route:
            return stop_history_index, route

        # If this is a journey that runs overnight, then the group_id will have the wrong date on it
        # We can try with yesterday's group id as well using a modified version of the avl
        modified_avl = {
            **avl,
            "date_of_journey": (
                date.fromisoformat(avl["date_of_journey"]) - timedelta(days=1)
            ).isoformat(),
        }

        stop_history_index_yesterday, route = self._get_timetable_for_group_id(
            avl_group_id(modified_avl),direction_ref, avl_time
        )
        if route:
            return stop_history_index_yesterday, route
        return stop_history_index, route
