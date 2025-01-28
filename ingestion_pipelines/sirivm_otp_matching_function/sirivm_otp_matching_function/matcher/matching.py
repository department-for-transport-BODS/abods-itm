import os
from collections.abc import Sequence
from datetime import datetime, timedelta
from math import asin, cos, radians, sin, sqrt
from typing import Protocol

from aws_lambda_powertools import Logger

from .models import (
    AVLRecord,
    GroupStopHistory,
    MatchedStop,
    PotentialMatch,
    RecordToAdd,
    RecordToRemove,
    RouteDetails,
    StopDetails,
    StopHistory,
    avl_group_id,
    avl_recorded_at_time_utc,
    stop_departure_time,
    stop_latitude,
    stop_longitude,
    stop_timetable_id,
)
from .utils import (
    get_otp_state,
    log_execution_time,
    timer,
    transform_coordinates_and_calculate_intersections,
    validate_date,
)


class TimetableStore(Protocol):
    """Interface for a timetable store"""

    def get_route_details(
        self,
        group_id: str,
        direction_ref: str,
    ) -> tuple[str, RouteDetails | None]:
        """
        Interface for getting the route data for a given group id and direction

        Args:
        ----
            group_id (str): A string representing operator_ref|line_name|journey_ref|date_of_journey in lower case
            direction_ref (str): Direction ref (e.g. inbound, outbound)

        Returns:
        -------
            str: The last index used to find the route in the timetable
            RouteDetails | None: The matched route data if any

        """
        ...


logger = Logger()

DISTANCE_THRESHOLD = 70
SAVED_MATCHES_LIMIT = 2
JOURNEY_STOPS_MIN_THRESHOLD = 3
ESTIMATED_MATCHING_TIME_UPPER_LIMIT_IN_SECONDS = 60
ESTIMATED_MATCHING_DISTANCE_UPPER_LIMIT_IN_METRES = 2000
MATCHING_TIME_LOWER_LIMIT_IN_SECONDS = -2 * 60 * 60
MATCHING_TIME_UPPER_LIMIT_IN_SECONDS = 1 * 60 * 60


def create_matched_stop(last_time_in_zone: datetime, is_estimate: bool) -> MatchedStop:  # noqa: FBT001
    return {"last_match_time": str(last_time_in_zone), "is_estimate": is_estimate}


def create_potential_match(
    avl: AVLRecord,
    distance: float,
) -> PotentialMatch:
    return {
        "last_distance": distance,
        "last_time_in_zone": str(avl_recorded_at_time_utc(avl)),
        "is_estimate": False,
    }


def haversine(avl: AVLRecord, stop: StopDetails) -> float:
    """
    Calculate the great circle distance in kilometers between two points on the earth (specified in decimal degrees)

    Args:
    ----
        avl (AVLRecord): Avl record
        stop (StopDetails): Details of a particular stop

    Returns:
    -------
        float: Distance between the avl and the stop

    """
    # convert decimal degrees to radians
    lat1, lon1 = float(avl["latitude"]), float(avl["longitude"])
    lat2, lon2 = stop_latitude(stop), stop_longitude(stop)

    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    r = 6371  # Radius of earth in kilometers. Use 3956 for miles. Determines return value units.
    return (c * r) * 1000


def get_lowest_matched_stop_index(group_stop_history: GroupStopHistory) -> int:
    """
    Get the lowest matched stop index if the matched stop list has 2 saved matches

    Args:
    ----
        group_stop_history (GroupStopHistory): Stop history of the current group id

    Returns:
    -------
        int: Lowest_matched_stop_index

    """
    matched_stops = group_stop_history["matched_stops"]
    # 11. Are there 2 actual matches already stored?
    if len(matched_stops) > 1:
        # 12. Select the lowest index of these 2 stops
        lowest_matched_stop_index = min(list(matched_stops.keys()), key=int)
    else:
        # 12. Select all stops
        lowest_matched_stop_index = 1
    return lowest_matched_stop_index


def check_estimated_match(
    avl: AVLRecord,
    group_stop_history: GroupStopHistory,
    stop: StopDetails,
) -> str | None:
    """
    Check if there is an estimated match between the current and previous avl points

    Args:
    ----
        avl (AVLRecord): Avl record
        group_stop_history (GroupStopHistory): Stop history of the current group id
        stop (StopDetails): Stop to check for match against

    """
    if os.getenv("ENABLE_ESTIMATED_MATCHING") != "true":
        return None

    if (
        (group_stop_history.get("last_avl_longitude") is None)
        or (group_stop_history.get("last_avl_latitude") is None)
        or not bool(group_stop_history.get("last_avl_time"))
    ):
        return None

    previous_avl_time = validate_date(group_stop_history["last_avl_time"][:19])

    time_diff = (avl_recorded_at_time_utc(avl) - previous_avl_time).total_seconds()

    if time_diff > ESTIMATED_MATCHING_TIME_UPPER_LIMIT_IN_SECONDS:
        return None

    stop_intersection_ratios = transform_coordinates_and_calculate_intersections(
        (stop_longitude(stop), stop_latitude(stop)),
        DISTANCE_THRESHOLD,
        (
            group_stop_history["last_avl_longitude"],
            group_stop_history["last_avl_latitude"],
        ),
        (avl["longitude"], avl["latitude"]),
        ESTIMATED_MATCHING_DISTANCE_UPPER_LIMIT_IN_METRES,
    )

    # check if the line intersects the circle twice
    if (
        len(stop_intersection_ratios) != 2  # noqa: PLR2004
    ):
        return None

    exit_time_factor = stop_intersection_ratios[1]

    exit_time = previous_avl_time + timedelta(
        seconds=exit_time_factor * time_diff,
    )

    return exit_time.isoformat()


def find_potential_matches(
    avl: AVLRecord,
    route_details: RouteDetails,
    group_stop_history: GroupStopHistory,
    final_stop_index: int,
) -> None:
    """
    Find potential matches after the last match

    Args:
    ----
        avl (AVLRecord): Avl record
        route_details (RouteDetails): Route stop info
        group_stop_history (GroupStopHistory): Stop history of the current group id
        final_stop_index (int): The stop index of the final stop

    """
    # 11-12. get the stop index to start for finding potential matches
    lowest_matched_stop_index = get_lowest_matched_stop_index(
        group_stop_history,
    )
    num_of_matched_stops = len(group_stop_history["matched_stops"])

    for i in range(int(lowest_matched_stop_index), final_stop_index + 1):
        # 12.1 Is there 1 actual match saved?
        # 12.2 Is the last stop index < 3 stops?
        # 12.3 Is this index less than 3/4*last stop index?
        if (
            num_of_matched_stops <= 1
            and final_stop_index > JOURNEY_STOPS_MIN_THRESHOLD
            and i > int(final_stop_index * 3 / 4)
        ):
            logger.debug(
                f"12.1/2/3 Number of matched stops is {num_of_matched_stops}, the final stop index {final_stop_index} > 3 and stop index {i} is greater than {int(final_stop_index * 3 / 4)} 3/4 of the final stop index. Skip stop {i} from being a potential match",
            )
            continue

        # final stop has already been matched, don't need to check for potentials
        if (
            i == final_stop_index
            and str(final_stop_index) in group_stop_history["matched_stops"]
        ):
            continue

        next_stop_details = route_details[str(i)]
        avl_next_stop_distance = haversine(avl, next_stop_details)
        # 13. If avl and the next stop distance < threshold
        if avl_next_stop_distance < DISTANCE_THRESHOLD:
            logger.debug(
                f"12. avl is {avl_next_stop_distance}m from stop {i}, less than {DISTANCE_THRESHOLD}m",
            )
            # 14. create potential match
            group_stop_history["potential_matches"][str(i)] = create_potential_match(
                avl,
                avl_next_stop_distance,
            )
            logger.debug(
                "13. potential match found",
                stop_index=i,
                potential_match=group_stop_history["potential_matches"][str(i)],
            )
        elif (
            i != final_stop_index
            and str(i) not in group_stop_history["potential_matches"]
            and str(i) not in group_stop_history["matched_stops"]
        ):
            timestamp_after_estimate = check_estimated_match(
                avl,
                group_stop_history,
                next_stop_details,
            )

            if timestamp_after_estimate:
                group_stop_history["potential_matches"][str(i)] = {
                    "last_distance": avl_next_stop_distance,
                    "last_time_in_zone": timestamp_after_estimate,
                    "is_estimate": True,
                }

    # update last avl time, longitude and latitude
    group_stop_history["last_avl_time"] = str(avl_recorded_at_time_utc(avl))
    group_stop_history["last_avl_longitude"] = avl["longitude"]
    group_stop_history["last_avl_latitude"] = avl["latitude"]


def check_update_first_stop(
    avl: AVLRecord,
    route_details: RouteDetails,
    group_stop_history: GroupStopHistory,
    stop_pos_distances_remove: list[RecordToRemove],
) -> None:
    """
    Check if the bus is going in and out from the first stop zone within 5 mins and update the record if it does

    Args:
    ----
        avl (AVLRecord): Avl record
        route_details (RouteDetails): Route stop info
        group_stop_history (GroupStopHistory): Stop history of the current group id
        stop_pos_distances_remove (list): The list of stops that needs to have matched records removed from database

    """
    logger.debug("check and update first stop")
    # Is the first stop matched?
    if "1" in group_stop_history["matched_stops"] and "1" in route_details:
        ms_index = "1"
        matched_stop_details = route_details[ms_index]
        ms_details = group_stop_history["matched_stops"][ms_index]
        ms_last_match_time = validate_date(ms_details["last_match_time"])
        avl_ms_distance = haversine(avl, matched_stop_details)
        if avl_ms_distance < DISTANCE_THRESHOLD:
            logger.debug(
                f"6+7. avl is {avl_ms_distance}m, within {DISTANCE_THRESHOLD}m",
            )
            difference = avl_recorded_at_time_utc(avl) - ms_last_match_time
            within_5_minutes = difference < timedelta(minutes=5)
            logger.debug(
                f"time diff = {difference}, {avl_recorded_at_time_utc(avl)}, {ms_last_match_time}, {within_5_minutes}",
            )
            # 8. if avl is within 5 mins after the last first stop matching time
            if within_5_minutes:
                logger.debug(
                    "8. Last match time is within 5 mins after recorded at time",
                )
                # 9.1 delete matched first stop
                del group_stop_history["matched_stops"][ms_index]
                # 9.2 set this match as a potential match
                group_stop_history["potential_matches"][ms_index] = (
                    create_potential_match(avl, avl_ms_distance)
                )
                logger.debug(
                    f"updated stop 1 potential match: {group_stop_history['potential_matches'][ms_index]}",
                )
                # 10. remove db matched details
                stop_pos_distances_remove.append(
                    {
                        "timetable_id": stop_timetable_id(matched_stop_details),
                        "group_id": avl_group_id(avl),
                    },
                )
                logger.debug(
                    "Removed matched first stop, and created new potential match",
                    stop_index=ms_index,
                    potential_match=group_stop_history["potential_matches"][ms_index],
                )


def find_matches_in_potential_matches(
    avl: AVLRecord,
    route_details: RouteDetails,
    group_stop_history: GroupStopHistory,
    stop_pos_distances: list[RecordToAdd],
    potential_matches_to_delete: list[str],
    final_stop_index: int,
    stop_pos_distances_remove: list[RecordToRemove],
) -> None:
    """
    Find matches within the potential match list

    Args:
    ----
        avl (AVLRecord): Avl record
        route_details (RouteDetails): Route stop info
        group_stop_history (GroupStopHistory): Stop history of the current group id
        stop_pos_distances (list): The matched records that is going to be written into the database
        potential_matches_to_delete (list): The list of matched stops to be removed from the potential match list
        final_stop_index (int): The stop index of the final stop
        stop_pos_distances_remove (list): The list of stops that needs to have matched records removed from database

    """
    logger.debug("14. iterating through potential matches")

    # Order potential matches by stop index to make sure stops are matched in order
    for pm_index in sorted(group_stop_history["potential_matches"].keys(), key=int):
        pm_details = group_stop_history["potential_matches"][pm_index]

        if pm_index not in route_details:
            return

        stop_details = route_details[pm_index]
        # calculate distance between avl and potential match stops
        avl_pm_distance = haversine(avl, stop_details)
        last_distance = pm_details["last_distance"]
        is_final_stop = int(pm_index) == final_stop_index
        # 15. If the distance between avl and potential match is less than threshold
        if avl_pm_distance < DISTANCE_THRESHOLD:
            logger.debug(
                f"15. avl is {avl_pm_distance}m from stop {pm_index}, less than {DISTANCE_THRESHOLD}m",
            )
            # 16. check if the potential match is the final stop of the route
            if is_final_stop:
                # 18-19. the final stop has not been matched yet and there is at least one match
                if (
                    pm_index not in group_stop_history["matched_stops"]
                    and len(group_stop_history["matched_stops"]) > 0
                ):
                    logger.debug(
                        f"16. {pm_index} is final stop and has not been matched",
                    )

                    move_potential_match_to_match(
                        final_stop_index,
                        route_details,
                        avl,
                        pm_index,
                        pm_details,
                        group_stop_history,
                        potential_matches_to_delete,
                        stop_pos_distances,
                        stop_pos_distances_remove,
                    )
            else:
                # 17.Update potential match with last_distance of as last distance from stop and last_time_in_zone of AVL time
                update_potential_match_with_recorded_at_time(
                    avl,
                    pm_index,
                    pm_details,
                    avl_pm_distance,
                )
        else:
            # 15. avl > distance threshold from potential match stop
            # Find one more row of avl that is away from the stop
            # 19. Check if pm last distance > distance threshold, 20. check if the avl potential distance > last distance
            logger.debug(
                f"15. avl is {avl_pm_distance}m from stop {pm_index}, greater than {DISTANCE_THRESHOLD}m",
            )
            if last_distance > DISTANCE_THRESHOLD and avl_pm_distance > last_distance:
                logger.debug(
                    f"19. Last distance {last_distance}m > {DISTANCE_THRESHOLD}m, 20. avl potential distance {avl_pm_distance}m > Last distance {last_distance}m",
                )
                # avl is confirmed to be getting away from the stop with last distance > 70m
                # 31-32. check if there is more than 1 match being created with the same recordedattime
                selected_index = select_potential_match_with_same_recordedattime(
                    pm_index,
                    group_stop_history,
                    potential_matches_to_delete,
                )
                if selected_index not in potential_matches_to_delete:
                    logger.debug(f"31-32. selected_index for matching {selected_index}")
                    move_potential_match_to_match(
                        final_stop_index,
                        route_details,
                        avl,
                        selected_index,
                        pm_details,
                        group_stop_history,
                        potential_matches_to_delete,
                        stop_pos_distances,
                        stop_pos_distances_remove,
                    )
            else:
                # 19. pm last distance < distance threshold / 20. the avl potential distance < last distance, Avl is moving backwards
                # 34. update potential match with current avl index and distance between potential match stop and avl location
                update_potential_match_without_recorded_at_time(
                    pm_index,
                    pm_details,
                    avl_pm_distance,
                )


def remove_matched_stops(
    group_stop_history: GroupStopHistory,
    matches_to_delete: list,
) -> None:
    """
    Remove matched stops from the potential match list

    Args:
    ----
        group_stop_history (GroupStopHistory): Stop history of the current group id
        delete_from (str): The name of the list to delete the matches from
        matches_to_delete (list): The list of matched stops to be removed

    """
    stops_list = group_stop_history["potential_matches"]
    if len(stops_list) > 0:
        matches_to_delete = set(matches_to_delete)
        for pm_index in matches_to_delete:
            del stops_list[pm_index]


def update_matched_stop(
    pm_index: str,
    last_time_in_zone: datetime,
    group_stop_history: GroupStopHistory,
    potential_matches_to_delete: list[str],
    is_estimate: bool,  # noqa: FBT001 - boolean argument is fine for now
) -> None:
    """
    Update last match, matched stops with current match and remove it from the potential match list

    Args:
    ----
        avl (AVLRecord): Avl record
        pm_index (str): Potential match stop index which has become a match
        last_time_in_zone (datetime): Potential match last time in zone
        group_stop_history (GroupStopHistory): Stop history of the current group id
        potential_matches_to_delete (list): The list of matched stops to be removed from the potential match list
        is_estimate (bool): Whether the match is an estimate

    """
    potential_matches_to_delete.append(pm_index)
    group_stop_history["matched_stops"][pm_index] = create_matched_stop(
        last_time_in_zone,
        is_estimate,
    )
    logger.debug(
        f"24. moved {pm_index} to matched stops, updated matched stop stop {pm_index}: {group_stop_history['matched_stops'][pm_index]}",
    )


def map_matched_stop_to_db(
    is_final_stop: bool,  # noqa: FBT001 - boolean argument is fine for now
    route_details: RouteDetails,
    stop_pos_distances: list[RecordToAdd],
    avl: AVLRecord,
    pm_index: str,
    last_time_in_zone: datetime | None,
    is_estimate: bool,  # noqa: FBT001 - boolean argument is fine for now
) -> None:
    """
    Update stop_pos_distances with the newly matched stop which will be written to the database

    Args:
    ----
        is_final_stop (bool): Current stop is a final stop
        route_details (RouteDetails): Route stop info
        stop_pos_distances (list): The matched records that is going to be written into the database
        avl (AVLRecord): The avl that caused the match
        pm_index (str): Potential match stop index which has become a match
        last_time_in_zone (datetime | None): Potential match last time in zone
        timestamp_after_estimate (datetime | None): Estimated match time
        is_estimate (bool): Whether the match is an estimate

    """
    timetable_departure_time = stop_departure_time(route_details[pm_index])
    time_difference = (last_time_in_zone - timetable_departure_time).total_seconds()

    if time_difference < MATCHING_TIME_LOWER_LIMIT_IN_SECONDS:
        logger.warning(
            "This match is more than 2 hours early",
            timetable_id=stop_timetable_id(route_details[pm_index]),
            time_difference=time_difference,
            last_time_in_zone=last_time_in_zone,
            timetable_departure_time=validate_date(timetable_departure_time),
        )
        return
    if time_difference > MATCHING_TIME_UPPER_LIMIT_IN_SECONDS:
        logger.warning(
            "This match is more than 1 hour late",
            timetable_id=stop_timetable_id(route_details[pm_index]),
            time_difference=time_difference,
            last_time_in_zone=last_time_in_zone,
            timetable_departure_time=validate_date(timetable_departure_time),
        )
    # 23. update db with potential match details
    stop_pos_distances.append(
        {
            "group_id": avl_group_id(avl),
            "stop_index": pm_index,
            "time_difference": time_difference,
            "last_time_in_zone_str": str(last_time_in_zone.strftime("%H:%M:%S"))
            if not is_estimate
            else None,
            "timetable_id": stop_timetable_id(route_details[pm_index]),
            "last_time_in_zone": last_time_in_zone if not is_estimate else None,
            "timestamp_after_estimate": last_time_in_zone if is_estimate else None,
            "otp_state": get_otp_state(is_final_stop, time_difference),
            "stop_type": "final" if is_final_stop else "Non-final",
        },
    )


def update_potential_match_without_recorded_at_time(
    pm_index: str,
    pm_details: PotentialMatch,
    avl_pm_distance: float,
) -> None:
    """
    Update potential match with last avl index, last distance and recorded at time if the current avl is outside the zone

    Args:
    ----
        avl (AVLRecord): Avl record
        pm_index (str): Potential match stop that needs to be updated
        pm_details (PotentialMatch): Potential match information stored in stop history
        avl_pm_distance (float): The distance between the avl record and the stop

    """
    pm_details["last_distance"] = avl_pm_distance
    logger.debug(
        "18. updated potential match",
        stop_index=pm_index,
        potential_match=pm_details,
    )


def update_potential_match_with_recorded_at_time(
    avl: AVLRecord,
    pm_index: str,
    pm_details: PotentialMatch,
    avl_pm_distance: float,
) -> None:
    """
    Update potential match with last avl index, last distance and recorded at time if the current avl is within the zone

    Args:
    ----
        avl (AVLRecord): Avl record
        pm_index (str): Potential match stop that needs to be updated
        pm_details (PotentialMatch): Potential match information stored in stop history
        avl_pm_distance (float): The distance between the avl record and the stop

    """
    pm_details["last_time_in_zone"] = str(avl_recorded_at_time_utc(avl))
    update_potential_match_without_recorded_at_time(
        pm_index,
        pm_details,
        avl_pm_distance,
    )


def select_potential_match_with_same_recordedattime(
    pm_index: str,
    group_stop_history: GroupStopHistory,
    potential_matches_to_delete: list[str],
) -> str:
    selected_index = pm_index
    if pm_index in potential_matches_to_delete:
        return pm_index
    int_keys = (int(key) for key in group_stop_history["matched_stops"])
    first_matched_stop = next(iter(sorted(int_keys)), 0)
    potential_matches = group_stop_history["potential_matches"]
    current_recordedattime = potential_matches[pm_index]["last_time_in_zone"]
    index_with_same_recordedattime = [
        ind
        for ind, pm in potential_matches.items()
        if pm["last_time_in_zone"] == current_recordedattime
        and ind not in potential_matches_to_delete
    ]
    # 31. Is there more than 1 match being created with the same recordedattime?
    if len(index_with_same_recordedattime) > 1:
        logger.debug(
            f"{pm_index} index_with_same_recordedattime: {index_with_same_recordedattime}",
        )
        lowest_index_diff = None
        # 32. Select the stop closest to the first actual in the sequence
        for index in index_with_same_recordedattime:
            diff = int(index) - first_matched_stop
            logger.debug(f"index: {index}, diff: {diff}")
            if not lowest_index_diff or diff < lowest_index_diff:
                lowest_index_diff = diff
                selected_index = index
            elif abs(int(index) - int(pm_index)) != 1:
                logger.debug(
                    f"32. {pm_index} and {index} have the same recorded at time, remove {index} from potential matches",
                )
                # remove the potential match(es) that are not the closest to the first actual matched
                potential_matches_to_delete.append(index)
    return selected_index


def move_potential_match_to_match(
    final_stop_index: int,
    route_details: RouteDetails,
    avl: AVLRecord,
    pm_index: str,
    pm_details: PotentialMatch,
    group_stop_history: GroupStopHistory,
    potential_matches_to_delete: list[str],
    stop_pos_distances: list[RecordToAdd],
    stop_pos_distances_remove: list[RecordToRemove],
) -> None:
    """
    Move the current potential match to be a match

    Args:
    ----
        final_stop_index (int): Final stop index
        route_details (RouteDetails): Route stop info
        avl (AVLRecord): Avl record
        pm_index (str): Potential match stop index which has become a match
        pm_details (PotentialMatch): Potential match information stored in stop history
        group_stop_history (GroupStopHistory): Stop history of the current group id
        potential_matches_to_delete (list): The list of matched stops to be removed from the potential match list
        stop_pos_distances (list): The matched records that is going to be written into the database
        stop_pos_distances_remove (list): The list of stops that needs to have matched records removed from database

    """
    is_final_stop = int(pm_index) == final_stop_index
    matched_stops = group_stop_history["matched_stops"]
    delete_potential_match = False
    last_time_in_zone = validate_date(pm_details["last_time_in_zone"])

    # 33. is this potential match the first match?
    if len(matched_stops) != 0:
        matched_stops_with_new_match = {
            **matched_stops,
            pm_index: create_matched_stop(
                last_time_in_zone,
                pm_details.get("is_estimate", False),
            ),
        }
        # 20. order saved matches by recorded_at_time
        ordered_matched_stops_with_new_match = dict(
            sorted(
                matched_stops_with_new_match.items(),
                key=lambda t: validate_date(t[1]["last_match_time"]).timestamp(),
            ),
        )
        stop_index_with_latest_match_timestamp = int(
            list(ordered_matched_stops_with_new_match.keys())[-1],
        )
        highest_matched_stop_index = int(max(matched_stops, key=lambda x: int(x)))
        lowest_matched_stop_index = int(min(matched_stops, key=lambda x: int(x)))
        # check if the new match index is higher than or equal to the highest index saved
        # 21-22. is the new match index higher than the highest index saved and Will this new match be the (saved match limit + 1) actual match saved
        if (
            int(pm_index) > highest_matched_stop_index
            and int(pm_index) == stop_index_with_latest_match_timestamp
            and len(matched_stops) == SAVED_MATCHES_LIMIT
        ):
            logger.debug(
                f"{pm_index} higher than highest_matched_stop_index {highest_matched_stop_index}, remove lowest matched stop from matched stops {lowest_matched_stop_index}",
            )
            logger.debug(
                "Matched stop identified for removal",
                stop_index=str(highest_matched_stop_index),
                matched_stop=group_stop_history["matched_stops"][
                    str(lowest_matched_stop_index)
                ],
            )
            # 23. Delete the lowest saved index from matched stops
            del group_stop_history["matched_stops"][str(lowest_matched_stop_index)]
        # 20. when the new match index is lower than the highest index saved
        # 28,29. Will this new match be the (saved match limit + 1) actual match saved and Is this new match the lowest index
        # 29.1 Do the two actual match index's saved have a difference of 1
        if (
            int(pm_index) <= lowest_matched_stop_index
            and (
                len(matched_stops) == SAVED_MATCHES_LIMIT
                or highest_matched_stop_index - lowest_matched_stop_index == 1
            )
        ) or (
            int(pm_index) > highest_matched_stop_index
            and int(pm_index) != stop_index_with_latest_match_timestamp
        ):
            logger.debug(
                f"{pm_index} lower than lowest_matched_stop_index {lowest_matched_stop_index}, remove it from potential matches",
            )
            # 30.Delete this new potential match
            potential_matches_to_delete.append(pm_index)
            delete_potential_match = True
        #  29. It's in the middle of the matched stop sequence or there's only one matched stop
        if int(pm_index) < highest_matched_stop_index and (
            int(pm_index) > lowest_matched_stop_index or len(matched_stops) == 1
        ):
            # 29.2 is the last stop in the matched stops ordered by recorded_at_time the final stop of the journey?
            if stop_index_with_latest_match_timestamp == final_stop_index:
                logger.debug(
                    f"last matched stop in new match sequence {stop_index_with_latest_match_timestamp} is final stop, remove lowest matched stop from matched stops {lowest_matched_stop_index}",
                )
                logger.debug(
                    "Matched stop identified for removal",
                    stop_index=str(highest_matched_stop_index),
                    matched_stop=group_stop_history["matched_stops"][
                        str(lowest_matched_stop_index)
                    ],
                )
                del group_stop_history["matched_stops"][str(lowest_matched_stop_index)]
            else:
                # 31.Delete the higher index stored from the db and json
                logger.debug(
                    f"{pm_index} lower than highest_matched_stop_index {highest_matched_stop_index}, remove matched stop index {highest_matched_stop_index} higher than {pm_index}",
                )
                logger.debug(
                    "Matched stop identified for removal",
                    stop_index=str(highest_matched_stop_index),
                    matched_stop=group_stop_history["matched_stops"][
                        str(highest_matched_stop_index)
                    ],
                )
                del group_stop_history["matched_stops"][str(highest_matched_stop_index)]
                stop_details = route_details.get(str(highest_matched_stop_index))
                if not stop_details:
                    logger.warning(
                        f"index {highest_matched_stop_index} doesn't exist in timetable, group_id: {avl_group_id(avl)}",
                    )
                else:
                    stop_pos_distances_remove.append(
                        {
                            "timetable_id": stop_timetable_id(stop_details),
                            "group_id": (avl_group_id(avl)),
                        },
                    )
    if not delete_potential_match:
        # 24. move potential match to be a match

        is_estimate = pm_details.get("is_estimate", False)
        update_matched_stop(
            pm_index,
            last_time_in_zone,
            group_stop_history,
            potential_matches_to_delete,
            is_estimate,
        )
        map_matched_stop_to_db(
            is_final_stop,
            route_details,
            stop_pos_distances,
            avl,
            pm_index,
            last_time_in_zone,
            is_estimate,
        )
        logger.debug(
            "Created matched stop from potential match",
            stop_index=pm_index,
            potential_match=pm_details,
            matched_stop=group_stop_history["matched_stops"][pm_index],
        )


def match_avl_batch(
    timetable: TimetableStore,
    avls: Sequence[AVLRecord],
    stop_history: StopHistory,
) -> tuple[Sequence[RecordToAdd], Sequence[RecordToRemove], StopHistory]:
    """
    Perform matching on a time sliced batch of AVL records.

    Args:
    ----
        timetable (Timetable): Timetable data
        avls (Sequence): A list of avl records
        stop_history (StopHistory): Full stop history of the specified shard.

    Returns:
    -------
        all_matched (Sequence): The matched stops which require updates in the database
        all_removed (Sequence): The matched stops that need to have matched records removed from database
        stop_history (StopHistory): The updated full stop history

    """
    all_matched: list[RecordToAdd] = []
    all_removed: list[RecordToRemove] = []
    with log_execution_time(logger, "match_avl_batch", avl_count=len(avls)):
        for avl in avls:
            to_add, to_remove, stop_history = match_avl(timetable, avl, stop_history)
            # After initially matching a stop, a later avl might provide evidence that the match was incorrect.
            # Each batch should contain only a single avl for a particular journey, and we can't see future avls
            # Therefore, the caller needs to add the match, and then wipe it if we determine that in a later batch.
            all_matched.extend(to_add)
            all_removed.extend(to_remove)

    logger.remove_keys(["avl", "group_id", "stop_history_index"])
    logger.info(
        "Processed batch",
        new_matches=len(all_matched),
        removed_matches=len(all_removed),
    )
    return all_matched, all_removed, stop_history


@timer(logger)
def match_group_id_avls(
    timetable: TimetableStore,
    avls: Sequence[AVLRecord],
    log_level: str | None = None,
) -> tuple[Sequence[RecordToAdd], int, int]:
    """
    Perform matching on all avls for a group_id.

    Args:
    ----
        timetable (Timetable): Timetable data
        avls (Sequence): A list of avl records for this group_id
        log_level (str): log_level

    Returns:
    -------
        journey_matches (Sequence): The matched stops which require updates in the database

    """
    if log_level:
        logger.setLevel(log_level)
    journey_matches: list[RecordToAdd] = []
    stop_history: StopHistory = {}
    for avl in avls:
        to_set, to_remove, stop_history = match_avl(
            timetable,
            avl,
            stop_history,
        )
        logger.debug(
            "Matched avl",
            to_set=to_set,
            to_remove=to_remove,
            stop_history=stop_history,
        )
        # After initially matching a stop, a later avl might provide evidence that the match was incorrect.
        # Here we can remove the prior match before the calling code has a chance to update the db.
        remove_timetable_ids = [rec["timetable_id"] for rec in to_remove]
        journey_matches = [
            rec
            for rec in journey_matches
            if rec["timetable_id"] not in remove_timetable_ids
        ]
        journey_matches.extend(to_set)
        logger.remove_keys(["avl", "group_id", "stop_history_index"])

    groups_and_directions = {(avl_group_id(avl), avl["direction_ref"]) for avl in avls}

    unprocessed_avls = 0
    expected_matched_stops = 0
    processed_route_indexes = set()
    for group_id, direction_ref in groups_and_directions:
        stop_history_index, route = timetable.get_route_details(group_id, direction_ref)
        avl_count = sum(
            1
            for avl in avls
            if len(groups_and_directions) == 1 or avl["direction_ref"] == direction_ref
        )

        if not route:
            logger.info(
                "Could not find timetable for some avls",
                group_id=group_id,
                direction_ref=direction_ref,
                avl_count=avl_count,
            )
            unprocessed_avls += avl_count
            continue
        expected_matched_stops += len(route)
        processed_route_indexes.add(stop_history_index)

    match_count = len({match["timetable_id"] for match in journey_matches})
    processed_routes = len(processed_route_indexes)
    logger.info(
        "Processed group_id",
        expected_stop_count=expected_matched_stops,
        processed_avls=len(avls) - unprocessed_avls,
        skipped_avls=unprocessed_avls,
        match_count=match_count,  # If this is ever different to match_length, then we should consider de-duplicating
        match_length=len(journey_matches),
        processed_routes=processed_routes,
    )

    return journey_matches, processed_routes, match_count


def match_avl(
    timetable: TimetableStore,
    avl: AVLRecord,
    stop_history: StopHistory,
) -> tuple[Sequence[RecordToAdd], Sequence[RecordToRemove], StopHistory]:
    """
    Given an AVL, compare to known stops in timetable, and return updated stop history, database updates to perform

    Args:
    ----
        timetable (Timetable): Timetable data
        avl (AVLRecord): A list of avl records
        stop_history (StopHistory): Full stop history of the specified shard.

    Returns:
    -------
        stop_pos_distances (Sequence): The matched stops which require updates in the database
        stop_pos_distances_remove (Sequence): The matched stops that need to have matched records removed from database
        stop_history (StopHistory): The updated full stop history

    """
    # 1. check if group id exists in timetable
    group_id = avl_group_id(avl)
    avl_direction = avl.get("direction_ref", "")
    stop_history_index, route_details = timetable.get_route_details(
        group_id,
        avl_direction,
    )

    logger.append_keys(
        avl=avl,
        group_id=group_id,
        stop_history_index=stop_history_index,
    )
    if not route_details:
        logger.debug("Could not find timetable for avl in timetable extract")
        return [], [], stop_history

    logger.debug(f"stop_history_index {stop_history_index} in timetable")

    # 2. check if group id exists in stop_history, if not, create a blank group stop history
    if stop_history_index not in stop_history:
        default_group_stop_history: GroupStopHistory = {
            "last_avl_time": "",
            "last_avl_longitude": None,
            "last_avl_latitude": None,
            "matched_stops": {},
            "potential_matches": {},
        }
        stop_history[stop_history_index] = default_group_stop_history
    group_stop_history = stop_history[stop_history_index]
    final_stop_index = len(route_details)
    current_avl_time = str(avl_recorded_at_time_utc(avl))

    # 3. check if current recorded_at_time is the same as the last avl time in group_stop_history
    if group_stop_history.get("last_avl_time") == current_avl_time:
        return [], [], stop_history

    stop_pos_distances_remove: list[RecordToRemove] = []
    # 4. update the time
    if len(group_stop_history["matched_stops"]) > 0:
        # 6-10. Check if the bus is revisiting stop 1
        check_update_first_stop(
            avl,
            route_details,
            group_stop_history,
            stop_pos_distances_remove,
        )

    # 11-14. Find potential matches
    logger.debug("11. find potential matches")

    find_potential_matches(
        avl,
        route_details,
        group_stop_history,
        final_stop_index,
    )

    # Check if avl is anywhere within the zone of a potential match
    # 14-34. Find matches
    if len(group_stop_history.get("potential_matches")) <= 0:
        return [], stop_pos_distances_remove, stop_history

    stop_pos_distances: list[RecordToAdd] = []
    potential_matches_to_remove = []
    find_matches_in_potential_matches(
        avl,
        route_details,
        group_stop_history,
        stop_pos_distances,
        potential_matches_to_remove,
        final_stop_index,
        stop_pos_distances_remove,
    )
    # 22.1 remove matched stops from potential matches
    remove_matched_stops(
        group_stop_history,
        potential_matches_to_remove,
    )

    return stop_pos_distances, stop_pos_distances_remove, stop_history
