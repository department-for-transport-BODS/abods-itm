from datetime import date, timedelta

from aws_lambda_powertools import Logger

from .models import (
    AVLRecord,
    Route,
    Timetable,
    avl_group_id,
    avl_recorded_at_time_utc,
    stop_departure_time,
)

logger = Logger()


class LiveTimetableStore:
    def __init__(self, timetable: Timetable, historic: bool = False) -> None:  # noqa: FBT001,FBT002 boolean arg just used to control logging, don't let it get out of hand
        self._timetable = timetable
        self._historic = historic

    def _get_timetable_by_index(
        self,
        timetable_index: str,
        avl: AVLRecord,
    ) -> Route | None:
        route = self._timetable.get(timetable_index)
        if not route:
            return None

        recorded_at_time = avl_recorded_at_time_utc(avl)

        # If the avl is more than 4 hours before the start of the journey, or more than 4 hours after the end, return nothing
        # This is mostly to help historic matching, and should never actually happen for live matching

        departure_times = [stop_departure_time(stop) for stop in route.values()]

        start_of_journey = min(departure_times)
        lower_bound = start_of_journey - timedelta(hours=4)
        if recorded_at_time < lower_bound:
            if not self._historic:
                logger.debug(
                    "AVL is more than 4 hours before the start of a matching journey in the extract",
                    timetable_index=timetable_index,
                    start_of_journey=start_of_journey,
                    lower_bound=lower_bound,
                    recorded_at_time=recorded_at_time,
                )
            return None

        end_of_journey = max(departure_times)
        upper_bound = end_of_journey + timedelta(hours=4)
        if recorded_at_time > upper_bound:
            if not self._historic:
                logger.warning(
                    "AVL is more than 4 hours after the end of a matching journey in the extract",
                    timetable_index=timetable_index,
                    end_of_journey=end_of_journey,
                    upper_bound=upper_bound,
                    recorded_at_time=recorded_at_time,
                )
            return None

        return route

    def _get_timetable_for_group_id(
        self,
        avl: AVLRecord,
    ) -> tuple[str, Route]:
        group_id = avl_group_id(avl)
        route_details = self._get_timetable_by_index(group_id, avl)
        if route_details:
            return group_id, route_details

        # In some cases, there can be multiple journeys with different directions using the same group id.
        # When that happens, sirivm_timetable_s3_generation_function will add the direction ref to the group id.
        # We will also need to use this to keep track of the matching for both journeys separately,
        # but the database updates need to be with the original group id
        index = group_id + "|" + avl["direction_ref"].lower()
        route_details = self._get_timetable_by_index(index, avl)

        return index, route_details

    def get_route(
        self,
        avl: AVLRecord,
    ) -> tuple[str, Route | None]:
        stop_history_index, route = self._get_timetable_for_group_id(
            avl,
        )
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
            modified_avl,
        )
        if route:
            return stop_history_index_yesterday, route
        return stop_history_index, route
