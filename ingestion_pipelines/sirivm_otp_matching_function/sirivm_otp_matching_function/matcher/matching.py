import os
from collections.abc import Sequence
from datetime import datetime, timedelta
from math import asin, cos, radians, sin, sqrt

from aws_lambda_powertools import Logger

from .matcher_config import config
from .models import AVLRecord, RouteDetails, StopDetails, Timetable
from .utils import (
    get_otp_state,
    get_time_difference,
    timer,
    validate_date,
)

logger = Logger()

distance_threshold = config.get("distance_threshold")
saved_matches_limit = config.get("saved_matches_limit")


def log_specific(avl: AVLRecord, log_message: str) -> None:
    """
    Enable logging for a specific service

    Args:
    ----
        avl (AVLRecord): Avl record
        log_message (str): Log message

    """
    if (
        "OPERATOR_REF" in os.environ
        and os.environ["OPERATOR_REF"] == avl.operator_ref
        and "LINE_NAME" in os.environ
        and os.environ["LINE_NAME"] == avl.line_name
    ):
        logger.info(log_message)


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
    lat1, lon1 = avl.latitude, avl.longitude
    lat2, lon2 = stop.latitude, stop.longitude

    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    r = 6371  # Radius of earth in kilometers. Use 3956 for miles. Determines return value units.
    return (c * r) * 1000


def get_lowest_matched_stop_index(group_stop_history: dict) -> int:
    """
    Get the lowest matched stop index if the matched stop list has 2 saved matches

    Args:
    ----
        group_stop_history (dict): Stop history of the current group id

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
        lowest_matched_stop_index = 0
    return lowest_matched_stop_index


def find_potential_matches(
    avl: AVLRecord,
    route_details: RouteDetails,
    group_stop_history: dict,
    current_avl_index: int,
    final_stop_index: int,
) -> None:
    """
    Find potential matches after the last match

    Args:
    ----
        avl (AVLRecord): Avl record
        route_details (RouteDetails): Route stop info
        group_stop_history (dict): Stop history of the current group id
        current_avl_index (int): Current avl index
        final_stop_index (int): The stop index of the final stop

    """
    # 11-12. get the stop index to start for finding potential matches
    lowest_matched_stop_index = get_lowest_matched_stop_index(group_stop_history)
    for i in range(int(lowest_matched_stop_index) + 1, final_stop_index + 1):
        next_stop_details = route_details[str(i)]
        avl_next_stop_distance = haversine(avl, next_stop_details)
        # 13. If avl and the next stop distance < threshold
        if avl_next_stop_distance < distance_threshold:
            log_specific(
                avl,
                f"12. avl is {avl_next_stop_distance}m from stop {i}, less than {distance_threshold}m",
            )
            # 14. create potential match
            group_stop_history["potential_matches"].update(
                {
                    str(i): {
                        "last_avl_index": current_avl_index,
                        "last_distance": avl_next_stop_distance,
                        "last_time_in_zone": avl.recorded_at_time_utc,
                    },
                },
            )
            log_specific(
                avl,
                f"13. potential match (stop{i}) created: {group_stop_history['potential_matches'][str(i)]}",
            )


def get_group_stop_history(group_id: str, stop_history: dict[str, dict]) -> dict:
    """
    Get stop history by the group id

    Args:
    ----
        group_id (str): Group id
        stop_history (dict[str, dict]): The full stop history

    Returns:
    -------
        dict: Stop history for the specified group id

    """
    return stop_history.setdefault(
        group_id,
        {
            "last_avl_time": "",
            "last_avl_index": 0,
            "matched_stops": {},
            "potential_matches": {},
        },
    )


def check_update_first_stop(
    avl: AVLRecord,
    route_details: RouteDetails,
    group_stop_history: dict,
    stop_pos_distances_remove: list[tuple],
    current_avl_index: int,
) -> None:
    """
    Check if the bus is going in and out from the first stop zone within 5 mins and update the record if it does

    Args:
    ----
        avl (AVLRecord): Avl record
        route_details (RouteDetails): Route stop info
        group_stop_history (dict): Stop history of the current group id
        stop_pos_distances_remove (list): The list of stops that needs to have matched records removed from database
        current_avl_index (int): Current avl index

    """
    log_specific(avl, "check and update first stop")
    # Is the first stop matched?
    if "1" in group_stop_history["matched_stops"] and "1" in route_details:
        ms_index = "1"
        matched_stop_details = route_details[ms_index]
        ms_details = group_stop_history["matched_stops"][ms_index]
        ms_last_match_time = validate_date(ms_details["last_match_time"])
        avl_ms_distance = haversine(avl, matched_stop_details)
        if avl_ms_distance < distance_threshold:
            log_specific(
                avl,
                f"6+7. avl is {avl_ms_distance}m, within {distance_threshold}m",
            )
            log_specific(
                avl,
                f"time diff = {avl.recorded_at_time_utc - ms_last_match_time}, {avl.recorded_at_time_utc}, {ms_last_match_time}, {avl.recorded_at_time_utc - ms_last_match_time < timedelta(minutes=5)}",
            )
            # 8. if avl is within 5 mins after the last first stop matching time
            if (avl.recorded_at_time_utc - ms_last_match_time) < timedelta(minutes=5):
                log_specific(
                    avl,
                    "8. Last match time is witin 5 mins after recorded at time",
                )
                # 9.1 delete matched first stop
                del group_stop_history["matched_stops"][ms_index]
                # 9.2 set this match as a potential match
                group_stop_history["potential_matches"].update(
                    {
                        ms_index: {
                            "last_avl_index": current_avl_index,
                            "last_distance": avl_ms_distance,
                            "last_time_in_zone": avl.recorded_at_time_utc,
                        },
                    },
                )
                log_specific(
                    avl,
                    f"updated stop 1 potential match: {group_stop_history['potential_matches'][ms_index]}",
                )
                # 10. remove db matched details
                stop_pos_distances_remove.append(
                    (ms_index, matched_stop_details.timetable_id, avl.group_id),
                )


def find_matches_in_potential_matches(
    avl: AVLRecord,
    route_details: RouteDetails,
    group_stop_history: dict,
    current_avl_index: int,
    batch_id: int,
    stop_pos_distances: dict[str, dict[str, tuple]],
    potential_matches_to_delete: list,
    final_stop_index: int,
    stop_pos_distances_remove: list[tuple],
) -> None:
    """
    Find matches within the potential match list

    Args:
    ----
        avl (AVLRecord): Avl record
        route_details (RouteDetails): Route stop info
        group_stop_history (dict): Stop history of the current group id
        current_avl_index (int): Current avl index
        batch_id (int): Avl batch id
        stop_pos_distances (dict): The matched records that is going to be written into the database
        potential_matches_to_delete (list): The list of matched stops to be removed from the potential match list
        final_stop_index (int): The stop index of the final stop
        stop_pos_distances_remove (list): The list of stops that needs to have matched records removed from database

    """
    # Order potential matches by stop index to make sure stops are matched in order
    potential_matches = dict(
        sorted(
            group_stop_history["potential_matches"].items(),
            key=lambda t: int(t[0]),
        ),
    )
    log_specific(avl, "14. iterating through potential matches")
    for pm_index, pm_details in potential_matches.items():
        if pm_index in route_details:
            stop_details = route_details[pm_index]
            # calculate distance between avl and potential match stops
            avl_pm_distance = haversine(avl, stop_details)
            last_distance = pm_details["last_distance"]
            is_final_stop = int(pm_index) == final_stop_index
            # 15. If the distance between avl and potential match is less than threshold
            if avl_pm_distance < distance_threshold:
                log_specific(
                    avl,
                    f"15. avl is {avl_pm_distance}m from stop {pm_index}, less than {distance_threshold}m",
                )
                # Distance between avl and potential match stop is less than threshold
                # 16. check if the potential match is the final stop of the route
                if is_final_stop:
                    # 18-19. the final stop has not been matched yet and there is at least one match
                    if (
                        pm_index not in group_stop_history["matched_stops"]
                        and len(group_stop_history["matched_stops"]) > 0
                    ):
                        log_specific(
                            avl,
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
                            batch_id,
                            stop_pos_distances_remove,
                        )
                else:
                    # 17.Update potential match with last_avl_index of current_index and last_distance of as last distance from stop and last_time_in_zone of AVL time
                    update_potential_match_with_recorded_at_time(
                        avl,
                        pm_index,
                        pm_details,
                        current_avl_index,
                        avl_pm_distance,
                    )
            else:
                # 15. avl > distance threshold from potential match stop
                # Find one more row of avl that is away from the stop
                # 19. Check if pm last distance > distance threshold, 20. check if the avl potential distance > last distance
                log_specific(
                    avl,
                    f"15. avl is {avl_pm_distance}m from stop {pm_index}, greater than {distance_threshold}m",
                )
                if (
                    last_distance > distance_threshold
                    and avl_pm_distance > last_distance
                ):
                    log_specific(
                        avl,
                        f"19. Last distance {last_distance}m > {distance_threshold}m, 20. avl potential distance {avl_pm_distance}m > Last distance {last_distance}m",
                    )
                    # avl is confirmed to be getting away from the stop with last distance > 70m
                    # 31-32. check if there is more than 1 match being created with the same recordedattime
                    selected_index = select_potential_match_with_same_recordedattime(
                        avl,
                        pm_index,
                        group_stop_history,
                        potential_matches_to_delete,
                    )
                    log_specific(
                        avl,
                        f"31-32. selected_index for matching {selected_index}",
                    )
                    move_potential_match_to_match(
                        final_stop_index,
                        route_details,
                        avl,
                        selected_index,
                        pm_details,
                        group_stop_history,
                        potential_matches_to_delete,
                        stop_pos_distances,
                        batch_id,
                        stop_pos_distances_remove,
                    )
                else:
                    # 19. pm last distance < distance threshold / 20. the avl potential distance < last distance, Avl is moving backwards
                    # 34. update potential match with current avl index and distance between potential match stop and avl location
                    update_potential_match_without_recorded_at_time(
                        avl,
                        pm_index,
                        pm_details,
                        current_avl_index,
                        avl_pm_distance,
                    )


def remove_matched_stops(
    group_stop_history: dict,
    delete_from: str,
    matches_to_delete: list,
) -> None:
    """
    Remove matched stops from the potential match/matched stops list

    Args:
    ----
        group_stop_history (dict): Stop history of the current group id
        delete_from (str): The name of the list to delete the matches from
        matches_to_delete (list): The list of matched stops to be removed

    """
    stops_list = group_stop_history[delete_from]
    if len(stops_list) > 0:
        matches_to_delete = set(matches_to_delete)
        for pm_index in matches_to_delete:
            del stops_list[pm_index]


def update_matched_stop(
    avl: AVLRecord,
    pm_index: str,
    last_time_in_zone: datetime,
    group_stop_history: dict,
    potential_matches_to_delete: list,
) -> None:
    """
    Update last match, matched stops with current match and remove it from the potential match list

    Args:
    ----
        avl (AVLRecord): Avl record
        pm_index (str): Potential match stop index which has become a match
        last_time_in_zone (datetime): Potential match last time in zone
        group_stop_history (dict): Stop history of the current group id
        potential_matches_to_delete (list): The list of matched stops to be removed from the potential match list

    """
    potential_matches_to_delete.append(pm_index)
    group_stop_history["matched_stops"].update(
        {pm_index: {"last_match_time": last_time_in_zone}},
    )
    log_specific(
        avl,
        f"24. moved {pm_index} to matched stops, updated matched stop stop {pm_index}: {group_stop_history['matched_stops'][pm_index]}",
    )


def write_matched_stop_to_db(
    is_final_stop: bool,  # noqa: FBT001 - boolean argument is fine for now
    route_details: RouteDetails,
    stop_pos_distances: dict[str, dict[str, tuple]],
    group_id: str,
    pm_index: str,
    last_time_in_zone: datetime,
    batch_id: int,
) -> None:
    """
    Update stop_pos_distances with the newly matched stop which will be written to the database

    Args:
    ----
        is_final_stop (bool): Current stop is a final stop
        route_details (RouteDetails): Route stop info
        stop_pos_distances (dict): The matched records that is going to be written into the database
        group_id (str): Group id
        pm_index (str): Potential match stop index which has become a match
        last_time_in_zone (datetime): Potential match last time in zone
        batch_id (int): Avl batch id

    """
    stop_details = route_details[pm_index]
    timetable_departure_time = route_details[pm_index].timetable_departure_time
    time_difference = get_time_difference(last_time_in_zone, timetable_departure_time)
    otp_state = get_otp_state(is_final_stop, time_difference)
    stop_type = "final" if is_final_stop else "Non-final"

    # 23. update db with potential match details
    stop_pos_distances[group_id].update(
        {
            pm_index: (
                time_difference,
                str(last_time_in_zone.strftime("%H:%M:%S")),
                stop_details.timetable_id,
                group_id,
                batch_id,
                last_time_in_zone,
                otp_state,
                stop_type,
            ),
        },
    )


def update_potential_match_without_recorded_at_time(
    avl: AVLRecord,
    pm_index: str,
    pm_details: dict,
    current_avl_index: int,
    avl_pm_distance: float,
) -> None:
    """
    Update potential match with last avl index, last distance and recorded at time if the current avl is outside the zone

    Args:
    ----
        avl (AVLRecord): Avl record
        pm_index (str): Potential match stop that needs to be updated
        pm_details (dict): Potential match information stored in stop history
        current_avl_index (int): Current avl index
        avl_pm_distance (float): The distance between the avl record and the stop

    """
    pm_details["last_avl_index"] = current_avl_index
    pm_details["last_distance"] = avl_pm_distance
    log_specific(
        avl,
        f"18. updated potential match {pm_index}: {pm_details}",
    )


def update_potential_match_with_recorded_at_time(
    avl: AVLRecord,
    pm_index: str,
    pm_details: dict,
    current_avl_index: int,
    avl_pm_distance: float,
) -> None:
    """
    Update potential match with last avl index, last distance and recorded at time if the current avl is within the zone

    Args:
    ----
        avl (AVLRecord): Avl record
        pm_index (str): Potential match stop that needs to be updated
        pm_details (dict): Potential match information stored in stop history
        current_avl_index (int): Current avl index
        avl_pm_distance (float): The distance between the avl record and the stop

    """
    pm_details["last_time_in_zone"] = avl.recorded_at_time_utc
    update_potential_match_without_recorded_at_time(
        avl,
        pm_index,
        pm_details,
        current_avl_index,
        avl_pm_distance,
    )


def select_potential_match_with_same_recordedattime(
    avl: AVLRecord,
    pm_index: str,
    group_stop_history: dict,
    potential_matches_to_delete: list,
) -> str:
    selected_index = pm_index
    if pm_index in potential_matches_to_delete:
        return pm_index
    matched_stops = dict(
        sorted(
            group_stop_history["matched_stops"].items(),
            key=lambda t: int(t[0]),
        ),
    )
    first_matched_stop = (
        next(iter(matched_stops.keys())) if len(matched_stops) > 1 else 0
    )
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
        log_specific(
            avl,
            f"{pm_index} index_with_same_recordedattime: {index_with_same_recordedattime}",
        )
        lowest_index_diff = None
        # 32. Select the stop closest to the first actual in the sequence
        for index in index_with_same_recordedattime:
            diff = int(index) - int(first_matched_stop)
            log_specific(avl, f"index: {index}, diff: {diff}")
            if not lowest_index_diff or diff < lowest_index_diff:
                lowest_index_diff = diff
                selected_index = index
            elif abs(int(index) - int(pm_index)) != 1:
                log_specific(
                    avl,
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
    pm_details: dict,
    group_stop_history: dict,
    potential_matches_to_delete: list,
    stop_pos_distances: dict[str, dict[str, tuple]],
    batch_id: int,
    stop_pos_distances_remove: list[tuple],
) -> None:
    """
    Move the current potential match to be a match

    Args:
    ----
        final_stop_index (int): Final stop index
        route_details (RouteDetails): Route stop info
        avl (AVLRecord): Avl record
        pm_index (str): Potential match stop index which has become a match
        pm_details (dict): Potential match information stored in stop history
        group_stop_history (dict): Stop history of the current group id
        potential_matches_to_delete (list): The list of matched stops to be removed from the potential match list
        stop_pos_distances (dict): The matched records that is going to be written into the database
        batch_id (int): Avl batch id
        stop_pos_distances_remove (list): The list of stops that needs to have matched records removed from database

    """
    is_final_stop = int(pm_index) == final_stop_index
    matched_stops = group_stop_history["matched_stops"]
    delete_potential_match = False
    last_time_in_zone = validate_date(pm_details["last_time_in_zone"])
    # 33. is this potential match the first match?
    if len(matched_stops) != 0:
        matched_stops_with_new_match = matched_stops.copy()
        matched_stops_with_new_match.update(
            {pm_index: {"last_match_time": last_time_in_zone}},
        )
        # 20. order saved matches by recorded_at_time
        ordered_matched_stops_with_new_match = dict(
            sorted(
                matched_stops_with_new_match.items(),
                key=lambda t: validate_date(t[1]["last_match_time"]).timestamp(),
            ),
        )
        new_highest_matched_stop_index = int(
            list(ordered_matched_stops_with_new_match.keys())[-1],
        )
        highest_matched_stop_index = int(max(matched_stops, key=lambda x: int(x)))
        lowest_matched_stop_index = int(min(matched_stops, key=lambda x: int(x)))
        # check if the new match index is higher than or equal to the highest index saved
        # 21-22. is the new match index higher than the highest index saved and Will this new match be the 3rd actual match saved
        if (
            int(pm_index) > highest_matched_stop_index
            and int(pm_index) == new_highest_matched_stop_index
            and len(matched_stops) == saved_matches_limit
        ):
            log_specific(
                avl,
                f"{pm_index} higher than highest_matched_stop_index {highest_matched_stop_index}, remove lowest matched stop from matched stops {lowest_matched_stop_index}",
            )
            # 23. Delete the lowest saved index from matched stops
            del group_stop_history["matched_stops"][str(lowest_matched_stop_index)]
        # 20. when the new match index is lower than the highest index saved
        # 28,29. Will this new match be the 3rd actual match saved and Is this new match the lowest index
        if (
            int(pm_index) < lowest_matched_stop_index
            and len(matched_stops) == saved_matches_limit
        ):
            log_specific(
                avl,
                f"{pm_index} lower than lowest_matched_stop_index {lowest_matched_stop_index}, remove it from potential matches",
            )
            # 30.Delete this new potential match
            potential_matches_to_delete.append(pm_index)
            delete_potential_match = True
        if (
            int(pm_index) < highest_matched_stop_index
            and int(pm_index) > lowest_matched_stop_index
        ):
            # 29.2 is the last stop in the matched stops ordered by recorded_at_time the final stop of the journey?
            if int(list(matched_stops.keys())[-1]) == final_stop_index:
                log_specific(
                    avl,
                    f"last matched stop {list(matched_stops.keys())[-1]} is final stop, remove lowest matched stop from matched stops {lowest_matched_stop_index}",
                )
                del group_stop_history["matched_stops"][str(lowest_matched_stop_index)]
            else:
                # 31.Delete the higher index stored from the db and json
                higher_indices_in_matched = [
                    ind
                    for ind in group_stop_history["matched_stops"]
                    if int(ind) > int(pm_index)
                ]
                log_specific(
                    avl,
                    f"{pm_index} lower than highest_matched_stop_index {highest_matched_stop_index}, remove matched stop index {higher_indices_in_matched} higher than {pm_index}",
                )
                for index in higher_indices_in_matched:
                    del group_stop_history["matched_stops"][index]
                    stop_details = route_details.get(index)
                    if not stop_details:
                        logger.warning(
                            f"index {index} doesn't exists in timetable, group_id: {avl.group_id}",
                        )
                        continue
                    stop_pos_distances_remove.append(
                        (index, stop_details.timetable_id, avl.group_id),
                    )
    if not delete_potential_match:
        # 24. move potential match to be a match
        update_matched_stop(
            avl,
            pm_index,
            last_time_in_zone,
            group_stop_history,
            potential_matches_to_delete,
        )
        write_matched_stop_to_db(
            is_final_stop,
            route_details,
            stop_pos_distances,
            avl.group_id,
            pm_index,
            last_time_in_zone,
            batch_id,
        )


@timer(logger)
def positions_timetable_lookup(
    timetable: Timetable,
    avl_dict: Sequence[AVLRecord],
    batch_id: int | None,
    stop_history: dict,
) -> tuple[dict[str, dict[str, tuple]], list[tuple], dict]:
    """
    For each AVL, compare to known stops in timetable, and return updated stop history, database updates to perform

    Args:
    ----
        timetable (dict): Timetable data
        avl_dict (list): A list of avl records
        batch_id (int, optional): Avl batch id.
        stop_history (dict): Full stop history of the specified shard.

    Returns:
    -------
        timetable_output (dict): The matched stops which require updates in the database
        stop_history (dict): The updated full stop history

    """
    stop_pos_distances = {}
    stop_pos_distances_remove = []
    for avl in avl_dict:
        # 1. check if group id exists in timetable
        if avl.group_id in timetable:
            stop_pos_distances.update({avl.group_id: {}})
            log_specific(avl, f"group_id {avl.group_id} in timetable")

            # 2. check if group id exists in stop_history, if not, create a blank group stop history
            group_stop_history = get_group_stop_history(avl.group_id, stop_history)
            current_avl_index = group_stop_history.get("last_avl_index")
            route_details = timetable[avl.group_id]
            final_stop_index = len(route_details)
            last_avl_time = group_stop_history.get("last_avl_time")
            # 3. check if current recorded_at_time is the same as the last avl time in group_stop_history
            if last_avl_time == "" or avl.recorded_at_time_utc != validate_date(
                last_avl_time,
            ):
                # 4. increment last avl index by 1 and update the time
                current_avl_index += 1
                group_stop_history["last_avl_index"] = current_avl_index
                # update last avl time
                group_stop_history["last_avl_time"] = avl.recorded_at_time_utc
                log_specific(avl, f"avl index {current_avl_index}")
                if len(group_stop_history["matched_stops"]) > 0:
                    # 6-10. Check if the bus is revisiting stop 1
                    check_update_first_stop(
                        avl,
                        route_details,
                        group_stop_history,
                        stop_pos_distances_remove,
                        current_avl_index,
                    )

                # 11-14. Find potential matches
                log_specific(avl, "11. find potential matches")
                find_potential_matches(
                    avl,
                    route_details,
                    group_stop_history,
                    current_avl_index,
                    final_stop_index,
                )

                # Check if avl is anywhere within the zone of a potential match
                # 14-34. Find matches
                if len(group_stop_history.get("potential_matches")) > 0:
                    potential_matches_to_remove = []
                    find_matches_in_potential_matches(
                        avl,
                        route_details,
                        group_stop_history,
                        current_avl_index,
                        batch_id or avl.batch_id,
                        stop_pos_distances,
                        potential_matches_to_remove,
                        final_stop_index,
                        stop_pos_distances_remove,
                    )
                    # 22.1 remove matched stops from potential matches
                    remove_matched_stops(
                        group_stop_history,
                        "potential_matches",
                        potential_matches_to_remove,
                    )
    return stop_pos_distances, stop_pos_distances_remove, stop_history
