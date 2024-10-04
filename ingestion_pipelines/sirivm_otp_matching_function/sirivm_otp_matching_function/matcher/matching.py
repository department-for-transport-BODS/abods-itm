from datetime import datetime, timedelta

from aws_lambda_powertools import Logger

from .find_potential_matches import find_potential_matches
from .matcher_config import config
from .models import AVLRecord
from .utils import (
    validate_date,
    log_specific,
    get_time_difference,
    haversine,
    get_otp_state,
    timer,
)
from typing import Any, Optional

logger = Logger()

distance_threshold = config.get("distance_threshold")
saved_matches_limit = config.get("saved_matches_limit")


def get_shard_filter(shards: dict, shard_no: str) -> list[str]:
    """Get a shard filter by a specified shard number

    Args:
        shard_no (str): Shard number assigned in s3 ingestion queue message

    Returns:
        list[str]: A list of operators in the specified shard
    """
    no_of_shards = len(shards["shards"])
    shard_filter = []
    if isinstance(shard_no, str):
        if shard_no == "0":
            for n in range(1, no_of_shards + 1):
                shard_filter.extend(shards["shards"][str(n)])
        elif int(shard_no) <= no_of_shards:
            shard_filter = shards["shards"][shard_no]
    else:
        logger.exception(f"shard_no {shard_no} data type {type(shard_no)} is not a str")
    return shard_filter


def get_group_stop_history(group_id: str, stop_history: dict[str, dict]) -> dict:
    """Get stop history by the group id

    Args:
        group_id (str): Group id
        stop_history (dict[str, dict]): The full stop history

    Returns:
        dict: Stop history for the specified group id
    """
    if group_id not in stop_history.keys():
        stop_history[group_id] = {
            "last_avl_time": "",
            "last_avl_index": 0,
            "matched_stops": {},
            "potential_matches": {},
        }
    group_stop_history = stop_history.get(group_id)
    return group_stop_history


def check_update_first_stop(
    avl: AVLRecord,
    timetable_dict: dict,
    group_stop_history: dict,
    stop_pos_distances_remove: list,
    current_avl_index: int,
) -> None:
    """Check if the bus is going in and out from the first stop zone within 5 mins and update the record if it does

    Args:
        avl (AVLRecord): Avl record
        timetable_dict (dict): Timetable data
        group_stop_history (dict): Stop history of the current group id
        stop_pos_distances_remove (list): The list of stops that needs to have matched records removed from database
        current_avl_index (int): Current avl index
    """
    log_specific(avl, "check and update first stop")
    # Is the first stop matched?
    if (
        "1" in group_stop_history["matched_stops"]
        and "1" in timetable_dict[avl.group_id]
    ):
        ms_index = "1"
        ms_latlong = timetable_dict[avl.group_id][ms_index][0]
        ms_details = group_stop_history["matched_stops"][ms_index]
        ms_last_match_time = validate_date(ms_details["last_match_time"])
        avl_ms_distance = haversine(avl, ms_latlong)
        if avl_ms_distance < distance_threshold:
            log_specific(
                avl,
                f"6+7. avl is {avl_ms_distance}m, within {distance_threshold}m",
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
                        }
                    }
                )
                log_specific(
                    avl,
                    f"updated stop 1 potential match: {group_stop_history['potential_matches'][ms_index]}",
                )
                # 10. remove db matched details
                timetable_id = timetable_dict[avl.group_id][ms_index][2]
                stop_pos_distances_remove.append((ms_index, timetable_id, avl.group_id))


def find_matches_in_potential_matches(
    avl: AVLRecord,
    timetable_dict: dict,
    group_stop_history: dict,
    current_avl_index: int,
    batch_id: str,
    stop_pos_distances: dict,
    potential_matches_to_delete: list,
    final_stop_index: int,
    stop_pos_distances_remove: list,
    matched_stops_to_remove: list,
) -> None:
    """Find matches within the potential match list

    Args:
        avl (AVLRecord): Avl record
        timetable_dict (dict): Timetable data
        group_stop_history (dict): Stop history of the current group id
        current_avl_index (int): Current avl index
        batch_id (str): Avl batch id
        stop_pos_distances (dict): The matched records that is going to be written into the database
        potential_matches_to_delete (list): The list of matched stops to be removed from the potential match list
        final_stop_index (int): The stop index of the final stop
        stop_pos_distances_remove (list): The list of stops that needs to have matched records removed from database
        matched_stops_to_remove (list): The list of stops that needs to have matched records removed from stop history
    """
    potential_matches = group_stop_history.get("potential_matches")
    log_specific(avl, "14. iterating through potential matches")
    for pm_index, pm_details in potential_matches.items():
        if pm_index in timetable_dict[avl.group_id]:
            # calculate distance between avl and potential match stops
            avl_pm_distance = haversine(avl, timetable_dict[avl.group_id][pm_index][0])
            last_distance = pm_details["last_distance"]
            is_final_stop = True if int(pm_index) == final_stop_index else False
            # 15. If the distance between avl and potential match is less than threshold
            if avl_pm_distance < distance_threshold:
                log_specific(
                    avl,
                    f"15. avl is {avl_pm_distance}m from stop {pm_index}, less than {distance_threshold}m",
                )
                # Distance between avl and potential match stop is less than threshold
                # 16. check if the potential match is the final stop of the route
                if is_final_stop:
                    # 18-19. the final stop has not been matched yet and there is more than 1 actual match stored
                    if (
                        pm_index not in group_stop_history["matched_stops"]
                        and len(group_stop_history["matched_stops"]) > 1
                    ):
                        log_specific(
                            avl,
                            f"16. {pm_index} is final stop and has not been matched",
                        )
                        move_potential_match_to_match(
                            is_final_stop,
                            timetable_dict,
                            avl,
                            pm_index,
                            pm_details,
                            group_stop_history,
                            potential_matches_to_delete,
                            stop_pos_distances,
                            batch_id,
                            stop_pos_distances_remove,
                            matched_stops_to_remove,
                        )
                else:
                    # 17.Update potential match with last_avl_index of current_index and last_distance of as last distance from stop and last_time_in_zone of AVL time
                    update_potential_match(
                        avl,
                        pm_index,
                        pm_details,
                        current_avl_index,
                        avl_pm_distance,
                        update_recorded_at_time=True,
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
                        pm_index, group_stop_history, potential_matches_to_delete
                    )
                    move_potential_match_to_match(
                        is_final_stop,
                        timetable_dict,
                        avl,
                        selected_index,
                        pm_details,
                        group_stop_history,
                        potential_matches_to_delete,
                        stop_pos_distances,
                        batch_id,
                        stop_pos_distances_remove,
                        matched_stops_to_remove,
                    )
                else:
                    # 19. pm last distance < distance threshold / 20. the avl potential distance < last distance, Avl is moving backwards
                    # 34. update potential match with current avl index and distance between potential match stop and avl location
                    update_potential_match(
                        avl,
                        pm_index,
                        pm_details,
                        current_avl_index,
                        avl_pm_distance,
                        update_recorded_at_time=False,
                    )


def remove_matched_stops(
    group_stop_history: dict, delete_from: str, matches_to_delete: list
) -> None:
    """Remove matched stops from the potential match/matched stops list

    Args:
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
    """Update last match, matched stops with current match and remove it from the potential match list

    Args:
        avl (AVLRecord): Avl record
        pm_index (str): Potential match stop index which has become a match
        last_time_in_zone (datetime): Potential match last time in zone
        group_stop_history (dict): Stop history of the current group id
        potential_matches_to_delete (list): The list of matched stops to be removed from the potential match list
    """
    potential_matches_to_delete.append(pm_index)
    group_stop_history["matched_stops"].update(
        {pm_index: {"last_match_time": last_time_in_zone}}
    )
    log_specific(
        avl,
        f"24. moved {pm_index} to matched stops, updated matched stop stop {pm_index}: {group_stop_history['matched_stops'][pm_index]}",
    )


def write_matched_stop_to_db(
    is_final_stop: bool,
    timetable_dict: dict,
    stop_pos_distances: dict,
    group_id: str,
    pm_index: str,
    last_time_in_zone: datetime,
    batch_id: str,
) -> None:
    """Update stop_pos_distances with the newly matched stop which will be written to the database

    Args:
        is_final_stop (bool): Current stop is a final stop
        timetable_dict (dict): Timetable data
        stop_pos_distances (dict): The matched records that is going to be written into the database
        group_id (str): Group id
        pm_index (str): Potential match stop index which has become a match
        last_time_in_zone (datetime): Potential match last time in zone
        batch_id (str): Avl batch id
    """
    timetable_id = timetable_dict[group_id][pm_index][2]
    timetable_departure_time = get_timetable_departure_time(
        timetable_dict, group_id, pm_index
    )
    time_difference = get_time_difference(last_time_in_zone, timetable_departure_time)
    if is_final_stop:
        otp_state = get_otp_state(True, time_difference)
        stop_type = "final"
    else:
        otp_state = get_otp_state(False, time_difference)
        stop_type = "Non-final"
    # 23. update db with potential match details
    stop_pos_distances[group_id].update(
        {
            pm_index: (
                time_difference,
                str(last_time_in_zone.strftime("%H:%M:%S")),
                timetable_id,
                group_id,
                batch_id,
                last_time_in_zone,
                otp_state,
                stop_type,
            )
        }
    )


def update_potential_match(
    avl: AVLRecord,
    pm_index: str,
    pm_details: dict,
    current_avl_index: int,
    avl_pm_distance: float,
    update_recorded_at_time: bool,
) -> None:
    """Update potential match with last avl index, last distance and recorded at time if the current avl is within the zone

    Args:
        avl (AVLRecord): Avl record
        pm_index (str): Potential match stop that needs to be updated
        pm_details (dict): Potential match information stored in stop history
        current_avl_index (int): Current avl index
        avl_pm_distance (float): The distance between the avl record and the stop
        update_recorded_at_time (bool): Whether recorded at time should be updated to the potential match
    """
    pm_details["last_avl_index"] = current_avl_index
    pm_details["last_distance"] = avl_pm_distance
    if update_recorded_at_time:
        pm_details["last_time_in_zone"] = avl.recorded_at_time_utc
    log_specific(
        avl,
        f"18. updated potential match {pm_index}: {pm_details}",
    )


def get_timetable_departure_time(
    timetable_dict: dict, group_id: str, pm_index: str
) -> datetime:
    """Get the expected departure time of the current potential stop

    Args:
        timetable_dict (dict): Timetable data
        group_id (str): Group id
        pm_index (str): Potential match stop index which has become a match

    Returns:
        datetime: Expected departure time of the current potential stop
    """
    expected_departure_time = timetable_dict[group_id][pm_index][1]
    timetable_date_of_journey = timetable_dict[group_id][pm_index][3]
    timetable_departure_time = f"{timetable_date_of_journey} {expected_departure_time}"
    return validate_date(timetable_departure_time)


def select_potential_match_with_same_recordedattime(
    pm_index: str, group_stop_history: dict, potential_matches_to_delete: list
) -> str:
    matched_stops = dict(
        sorted(group_stop_history["matched_stops"].items(), key=lambda t: int(t[0]))
    )
    if len(matched_stops) > 1:
        first_matched_stop = list(matched_stops.keys())[0]
    else:
        first_matched_stop = 0
    potential_matches = group_stop_history["potential_matches"]
    current_recordedattime = potential_matches[pm_index]["last_time_in_zone"]
    index_with_same_recordedattime = [
        ind
        for ind, pm in potential_matches.items()
        if pm["last_time_in_zone"] == current_recordedattime
    ]
    selected_index = pm_index
    # 31. Is there more than 1 match being created with the same recordedattime?
    if len(index_with_same_recordedattime) > 1:
        lowest_index_diff = None
        # 32. Select the stop closest to the first actual in the sequence
        for index in index_with_same_recordedattime:
            diff = int(index) - int(first_matched_stop)
            if not lowest_index_diff or diff < lowest_index_diff:
                lowest_index_diff = diff
                selected_index = index
            else:
                # remove the potential match(es) that are not the closest to the first actual matched
                potential_matches_to_delete.append(index)
    return selected_index


def move_potential_match_to_match(
    is_final_stop: bool,
    timetable_dict: dict,
    avl: AVLRecord,
    pm_index: str,
    pm_details: dict,
    group_stop_history: dict,
    potential_matches_to_delete: list,
    stop_pos_distances: dict,
    batch_id: str,
    stop_pos_distances_remove: list,
    matched_stops_to_remove: list,
) -> None:
    """Move the current potential match to be a match

    Args:
        is_final_stop (bool): Current stop is a final stop
        timetable_dict (dict): Timetable data
        avl (AVLRecord): Avl record
        pm_index (str): Potential match stop index which has become a match
        pm_details (dict): Potential match information stored in stop history
        group_stop_history (dict): Stop history of the current group id
        potential_matches_to_delete (list): The list of matched stops to be removed from the potential match list
        stop_pos_distances (dict): The matched records that is going to be written into the database
        batch_id (str): Avl batch id
        stop_pos_distances_remove (list): The list of stops that needs to have matched records removed from database
        matched_stops_to_remove (list): The list of stops that needs to have matched records removed from stop history
    """

    matched_stops = dict(
        sorted(
            group_stop_history["matched_stops"].items(),
            key=lambda t: t[1]["last_match_time"],
        )
    )
    delete_potential_match = False
    last_time_in_zone = validate_date(pm_details["last_time_in_zone"])
    # 33. is this potential match the first match?
    if len(matched_stops) != 0:
        matched_stops_with_new_match = matched_stops.copy()
        matched_stops_with_new_match.update(
            {pm_index: {"last_match_time": last_time_in_zone}}
        )
        # 20. order saved matches by recorded_at_time
        ordered_matched_stops_with_new_match = dict(
            sorted(
                matched_stops_with_new_match.items(),
                key=lambda t: t[1]["last_match_time"],
            )
        )
        new_highest_matched_stop_index = int(
            list(ordered_matched_stops_with_new_match.keys())[-1]
        )
        highest_matched_stop_index = int(max(matched_stops, key=lambda x: int(x)))
        lowest_matched_stop_index = int(min(matched_stops, key=lambda x: int(x)))
        # check if the new match index is higher than or equal to the highest index saved
        # 21-22. is the new match index higher than the highest index saved and Will this new match be the 3rd actual match saved
        if len(ordered_matched_stops_with_new_match) == saved_matches_limit:
            if (
                int(pm_index) > highest_matched_stop_index
                and int(pm_index) == new_highest_matched_stop_index
                # and len(ordered_matched_stops_with_new_match) == saved_matches_limit
            ):
                # 23. Delete the lowest saved index from matched stops
                matched_stops_to_remove.append(str(lowest_matched_stop_index))
            # 20. when the new match index is lower than the highest index saved
            # 28,29. Will this new match be the 3rd actual match saved and Is this new match the lowest index
            if (
                int(pm_index) < lowest_matched_stop_index
                # and len(ordered_matched_stops_with_new_match) == saved_matches_limit
            ):
                log_specific(
                    avl,
                    f"{pm_index} lower than lowest_matched_stop_index {lowest_matched_stop_index}",
                )
                # 30.Delete this new potential match
                potential_matches_to_delete.append(pm_index)
                delete_potential_match = True
            else:
                # 31.Delete the higher index stored from the db and json
                higher_indices_in_matched = [
                    ind
                    for ind in group_stop_history["matched_stops"]
                    if int(ind) > int(pm_index)
                ]
                for index in higher_indices_in_matched:
                    matched_stops_to_remove.append(index)
                    timetable_id = timetable_dict[avl.group_id][index][2]
                    stop_pos_distances_remove.append(
                        (index, timetable_id, avl.group_id)
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
            timetable_dict,
            stop_pos_distances,
            avl.group_id,
            pm_index,
            last_time_in_zone,
            batch_id,
        )


@timer(logger)
def positions_timetable_lookup(
    timetable_dict: dict,
    shards: dict,
    shard_no: str,
    avl_dict: list[AVLRecord],
    batch_id: Optional[str],
    stop_history: dict,
) -> (dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict):
    """Main function for matching, get avl record and compare it with the stops in timetable

    Args:
        timetable_dict (dict): Timetable data
        shard_no (str): Shard number assigned
        avl_dict (list): A list of avl records
        timetable_output (dict): Timetable data
        batch_id (str, optional): Avl batch id. Defaults to None.
        stop_history (dict, optional): Full stop history of the specified shard. Defaults to {}.

    Returns:
        timetable_output (dict): The matched stops which require updates in the database
        stop_history (dict): The updated full stop history
    """
    stop_pos_distances = {}
    stop_pos_distances_remove = []
    shard_filter = get_shard_filter(shards, shard_no)
    for avl in avl_dict:
        if (shard_no != "0" and avl.operator_ref in shard_filter) or (
            shard_no == "0" and avl.operator_ref not in shard_filter
        ):
            # 1. check if group id exists in timetable
            if avl.group_id in timetable_dict.keys():
                stop_pos_distances.update({avl.group_id: {}})
                log_specific(avl, f"group_id {avl.group_id} in timetable")

                # 2. check if group id exists in stop_history, if not, create a blank group stop history
                group_stop_history = get_group_stop_history(avl.group_id, stop_history)
                current_avl_index = group_stop_history.get("last_avl_index")
                final_stop_index = len(timetable_dict[avl.group_id])
                last_avl_time = group_stop_history.get("last_avl_time")
                # 3. check if current recorded_at_time is the same as the last avl time in group_stop_history
                # ! recorded at time > last avl time?
                if last_avl_time == "" or avl.recorded_at_time_utc != validate_date(
                    last_avl_time
                ):
                    # 4. increment last avl index by 1 and update the time
                    current_avl_index += 1
                    group_stop_history["last_avl_index"] = current_avl_index
                    # update last avl time
                    group_stop_history["last_avl_time"] = avl.recorded_at_time_utc
                    if len(group_stop_history["matched_stops"]) > 0:
                        # 6-10. Check if the bus is revisiting stop 1
                        check_update_first_stop(
                            avl,
                            timetable_dict,
                            group_stop_history,
                            stop_pos_distances_remove,
                            current_avl_index,
                        )

                    # 11-14. Find potential matches
                    log_specific(avl, "11. find potential matches")
                    find_potential_matches(
                        avl,
                        timetable_dict,
                        group_stop_history,
                        current_avl_index,
                        final_stop_index,
                    )

                    # Check if avl is anywhere within the zone of a potential match
                    # 14-34. Find matches
                    if len(group_stop_history.get("potential_matches")) > 0:
                        potential_matches_to_remove = []
                        matched_stops_to_remove = []
                        find_matches_in_potential_matches(
                            avl,
                            timetable_dict,
                            group_stop_history,
                            current_avl_index,
                            batch_id,
                            stop_pos_distances,
                            potential_matches_to_remove,
                            final_stop_index,
                            stop_pos_distances_remove,
                            matched_stops_to_remove,
                        )
                        # 22.1 remove matched stops from potential matches
                        remove_matched_stops(
                            group_stop_history,
                            "potential_matches",
                            potential_matches_to_remove,
                        )
                        remove_matched_stops(
                            group_stop_history, "matched_stops", matched_stops_to_remove
                        )
    timetable_output["set"].update(stop_pos_distances)
    timetable_output["remove"].extend(stop_pos_distances_remove)
    return timetable_output, stop_history
