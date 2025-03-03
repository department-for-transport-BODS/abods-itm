from datetime import date, timedelta

from .models import AVLRecord, Route, Timetable, avl_group_id


class LiveTimetableStore:
    """Timetable store used for live matching"""

    def __init__(self, timetable: Timetable) -> None:
        """Construct a live timetable store"""
        self._timetable = timetable

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

        def get_timetable_for_group_id(group_id: str) -> tuple[str, Route]:
            route_details = self._timetable.get(group_id)
            if route_details:
                return group_id, route_details

            # In some cases, there can be multiple journeys with different directions using the same group id.
            # When that happens, sirivm_timetable_s3_generation_function will add the direction ref to the group id.
            # We will also need to use this to keep track of the matching for both journeys separately,
            # but the database updates need to be with the original group id
            index = group_id + "|" + direction_ref.lower()
            route_details = self._timetable.get(index)

            return index, route_details

        stop_history_index, route = get_timetable_for_group_id(avl_group_id(avl))
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

        stop_history_index_yesterday, route = get_timetable_for_group_id(
            avl_group_id(modified_avl),
        )
        if route:
            return stop_history_index_yesterday, route
        return stop_history_index, route
