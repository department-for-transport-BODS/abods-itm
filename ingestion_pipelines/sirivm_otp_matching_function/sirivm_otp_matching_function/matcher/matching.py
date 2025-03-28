import os
from collections.abc import Sequence
from datetime import datetime, timedelta
from math import asin, cos, radians, sin, sqrt
from typing import Protocol

from aws_lambda_powertools import Logger
from shared.config import (
    END_OF_JOURNEY_PROPORTION,
    ESTIMATED_MATCHING_DISTANCE_UPPER_LIMIT_IN_METRES,
    ESTIMATED_MATCHING_TIME_UPPER_LIMIT_IN_SECONDS,
    MATCHING_TIME_LOWER_LIMIT_IN_SECONDS,
    MATCHING_TIME_UPPER_LIMIT_IN_SECONDS,
    MATCH_ZONE_RADIUS_IN_METERS,
    RADIUS_OF_EARTH_IN_METERS,
    SAVED_MATCHES_LIMIT,
    SHORT_JOURNEY_STOP_COUNT,
)

from .models import (
    AVLRecord,
    BadDbMatch,
    MatchedStop,
    NewDbMatch,
    PotentialMatch,
    Route,
    RouteHistory,
    Stop,
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
    def get_route(
        self,
        avl: AVLRecord,
    ) -> tuple[str, Route | None]: ...


logger = Logger()


def get_final_stop_index(route: Route) -> int:
    return len(route)


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


def distance_from_stop(avl: AVLRecord, stop: Stop) -> float:
    """Calculate the distance in meters between an avl and a stop"""
    # convert decimal degrees to radians
    lat1, lon1 = float(avl["latitude"]), float(avl["longitude"])
    lat2, lon2 = stop_latitude(stop), stop_longitude(stop)

    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return c * RADIUS_OF_EARTH_IN_METERS


def get_lowest_matched_stop_index(route_history: RouteHistory) -> int:
    """Get the lowest matched stop index if the matched stop list has 2 saved matches"""
    matched_stops = route_history["matched_stops"]
    # 11. Are there 2 actual matches already stored?

    if len(matched_stops) <= 1:
        # 12. Select all stops
        return 1

    # 12. Select the lowest index of these 2 stops
    return min(int(index) for index in matched_stops)


def check_estimated_match(  # noqa: PLR0911 - it's not that many returns
    avl: AVLRecord,
    route_history: RouteHistory,
    stop: Stop,
) -> str | None:
    """Check if there is an estimated match between the current and previous avl points"""
    if os.getenv("ENABLE_ESTIMATED_MATCHING") != "true":
        return None

    if route_history.get("last_avl_longitude") is None:
        return None

    if route_history.get("last_avl_latitude") is None:
        return None

    if not bool(route_history.get("last_avl_time")):
        return None

    previous_avl_time = validate_date(route_history["last_avl_time"][:19])

    time_diff = (avl_recorded_at_time_utc(avl) - previous_avl_time).total_seconds()

    if time_diff > ESTIMATED_MATCHING_TIME_UPPER_LIMIT_IN_SECONDS:
        return None

    stop_intersection_ratios = transform_coordinates_and_calculate_intersections(
        (stop_longitude(stop), stop_latitude(stop)),
        MATCH_ZONE_RADIUS_IN_METERS,
        (
            route_history["last_avl_longitude"],
            route_history["last_avl_latitude"],
        ),
        (avl["longitude"], avl["latitude"]),
        ESTIMATED_MATCHING_DISTANCE_UPPER_LIMIT_IN_METRES,
    )

    # check if the line intersects the circle twice
    if len(stop_intersection_ratios) != 2:  # noqa: PLR2004
        return None

    exit_time_factor = stop_intersection_ratios[1]

    exit_time = previous_avl_time + timedelta(
        seconds=exit_time_factor * time_diff,
    )

    return exit_time.isoformat()


def find_potential_matches(
    avl: AVLRecord,
    route: Route,
    route_history: RouteHistory,
) -> None:
    """Find potential matches after the last match"""
    # 11-12. get the stop index to start for finding potential matches
    lowest_matched_stop_index = get_lowest_matched_stop_index(route_history)
    num_of_matched_stops = len(route_history["matched_stops"])

    final_stop_index = get_final_stop_index(route)
    for stop_index_int in range(lowest_matched_stop_index, final_stop_index + 1):
        stop_index = str(stop_index_int)

        # 12.1 Is there 1 actual match saved?
        # 12.2 Is the last stop index < 3 stops?
        # 12.3 Is this index less than 3/4*last stop index?
        if (
            num_of_matched_stops <= 1
            and final_stop_index > SHORT_JOURNEY_STOP_COUNT
            and stop_index_int > int(final_stop_index * END_OF_JOURNEY_PROPORTION)
        ):
            logger.debug(
                f"12.1/2/3 Number of matched stops is {num_of_matched_stops}, the final stop index {final_stop_index} > 3 and stop index {stop_index} is greater than {int(final_stop_index * 3 / 4)} 3/4 of the final stop index. Skip stop {stop_index} from being a potential match",
            )
            continue

        # final stop has already been matched, don't need to check for potentials
        if (
            stop_index_int == final_stop_index
            and str(final_stop_index) in route_history["matched_stops"]
        ):
            continue

        stop = route[stop_index]
        stop_distance_in_meters = distance_from_stop(avl, stop)
        # 13. If avl and the next stop distance < threshold
        if stop_distance_in_meters < MATCH_ZONE_RADIUS_IN_METERS:
            logger.debug(
                f"12. avl is {stop_distance_in_meters}m from stop {stop_index}, less than {MATCH_ZONE_RADIUS_IN_METERS}m",
            )
            # 14. create potential match
            potential_match = create_potential_match(avl, stop_distance_in_meters)
            route_history["potential_matches"][stop_index] = potential_match
            logger.debug(
                "13. potential match found",
                stop_index=stop_index,
                potential_match=potential_match,
            )
            continue

        if stop_index_int == final_stop_index:
            continue

        if stop_index in route_history["potential_matches"]:
            continue

        if stop_index in route_history["matched_stops"]:
            continue

        timestamp_after_estimate = check_estimated_match(avl, route_history, stop)

        if not timestamp_after_estimate:
            continue

        potential_match: PotentialMatch = {
            "last_distance": stop_distance_in_meters,
            "last_time_in_zone": timestamp_after_estimate,
            "is_estimate": True,
        }
        route_history["potential_matches"][stop_index] = potential_match


def check_update_first_stop(
    avl: AVLRecord,
    route: Route,
    route_history: RouteHistory,
    bad_matches: list[BadDbMatch],
) -> None:
    """Check if the bus is going in and out from the first stop zone within 5 mins and update the record if it does"""
    logger.debug("check and update first stop")

    # Is the first stop matched?
    stop_index = "1"
    if stop_index not in route_history["matched_stops"]:
        return

    if stop_index not in route:
        return

    stop = route[stop_index]
    stop_distance_in_meters = distance_from_stop(avl, stop)

    if stop_distance_in_meters >= MATCH_ZONE_RADIUS_IN_METERS:
        return

    matched_stop = route_history["matched_stops"][stop_index]
    matched_stop_time = validate_date(matched_stop["last_match_time"])

    logger.debug(
        f"6+7. avl is {stop_distance_in_meters}m, within {MATCH_ZONE_RADIUS_IN_METERS}m",
    )
    time_since_match = avl_recorded_at_time_utc(avl) - matched_stop_time
    within_5_minutes = time_since_match < timedelta(minutes=5)
    logger.debug(
        f"time diff = {time_since_match}, {avl_recorded_at_time_utc(avl)}, {matched_stop_time}, {within_5_minutes}",
    )

    # 8. if avl is within 5 mins after the last first stop matching time
    if not within_5_minutes:
        return

    logger.debug("8. Last match time is within 5 mins after recorded at time")
    # 9.1 delete matched first stop
    del route_history["matched_stops"][stop_index]
    # 9.2 set this match as a potential match
    potential_match = create_potential_match(avl, stop_distance_in_meters)
    route_history["potential_matches"][stop_index] = potential_match
    logger.debug(f"updated stop 1 potential match: {potential_match}")
    # 10. remove db matched details
    bad_match: BadDbMatch = {"timetable_id": stop_timetable_id(stop)}
    bad_matches.append(bad_match)
    logger.debug(
        "Removed matched first stop, and created new potential match",
        stop_index=stop_index,
        potential_match=potential_match,
    )


def find_matches_in_potential_matches(
    avl: AVLRecord,
    route: Route,
    route_history: RouteHistory,
    new_matches: list[NewDbMatch],
    potential_matches_to_delete: list[str],
    bad_matches: list[BadDbMatch],
) -> None:
    """Find matches within the potential match list"""
    logger.debug("14. iterating through potential matches")

    # Order potential matches by stop index to make sure stops are matched in order
    final_stop_index = get_final_stop_index(route)
    for stop_index in sorted(route_history["potential_matches"].keys(), key=int):
        if stop_index not in route:
            return

        stop_details = route[stop_index]
        potential_match = route_history["potential_matches"][stop_index]
        # calculate distance between avl and potential match stops
        stop_distance_in_meters = distance_from_stop(avl, stop_details)
        is_final_stop = int(stop_index) == final_stop_index
        # 15. If the distance between avl and potential match is less than threshold
        vehicle_within_stop_match_zone = (
            stop_distance_in_meters < MATCH_ZONE_RADIUS_IN_METERS
        )
        if vehicle_within_stop_match_zone:
            logger.debug(
                f"15. avl is {stop_distance_in_meters}m from stop {stop_index}, less than {MATCH_ZONE_RADIUS_IN_METERS}m",
            )
            # 16. check if the potential match is the final stop of the route
            if not is_final_stop:
                # 17.Update potential match with last_distance of as last distance from stop and last_time_in_zone of AVL time
                update_potential_match_with_recorded_at_time(
                    avl,
                    stop_index,
                    potential_match,
                    stop_distance_in_meters,
                )
                continue

            if stop_index in route_history["matched_stops"]:
                continue

            if len(route_history["matched_stops"]) <= 0:
                continue

            # 18-19. the final stop has not been matched yet and there is at least one match
            logger.debug(
                f"16. {stop_index} is final stop and has not been matched",
            )

            move_potential_match_to_match(
                route,
                avl,
                stop_index,
                potential_match,
                route_history,
                potential_matches_to_delete,
                new_matches,
                bad_matches,
            )
            continue

        # 15. avl > distance threshold from potential match stop
        # Find one more row of avl that is away from the stop
        # 19. Check if pm last distance > distance threshold, 20. check if the avl potential distance > last distance
        logger.debug(
            f"15. avl is {stop_distance_in_meters}m from stop {stop_index}, greater than {MATCH_ZONE_RADIUS_IN_METERS}m",
        )
        last_distance = potential_match["last_distance"]
        vehicle_moving_toward_stop = stop_distance_in_meters <= last_distance
        last_distance_in_stop_zone = last_distance <= MATCH_ZONE_RADIUS_IN_METERS
        if last_distance_in_stop_zone or vehicle_moving_toward_stop:
            # 19. pm last distance < distance threshold / 20. the avl potential distance < last distance, Avl is moving backwards
            # 34. update potential match with current avl index and distance between potential match stop and avl location
            update_potential_match_without_recorded_at_time(
                stop_index,
                potential_match,
                stop_distance_in_meters,
            )
            continue

        logger.debug(
            f"19. Last distance {last_distance}m > {MATCH_ZONE_RADIUS_IN_METERS}m, "
            f"20. avl potential distance {stop_distance_in_meters}m > Last distance {last_distance}m",
        )
        # avl is confirmed to be getting away from the stop with last distance > 70m
        # 31-32. check if there is more than 1 match being created with the same recordedattime
        selected_index = select_potential_match_with_same_recordedattime(
            stop_index,
            route_history,
            potential_matches_to_delete,
        )

        if selected_index in potential_matches_to_delete:
            continue

        logger.debug(f"31-32. selected_index for matching {selected_index}")
        move_potential_match_to_match(
            route,
            avl,
            selected_index,
            potential_match,
            route_history,
            potential_matches_to_delete,
            new_matches,
            bad_matches,
        )


def remove_matched_stops(
    route_history: RouteHistory,
    matches_to_delete: list,
) -> None:
    """Remove matched stops from the potential match list"""
    stops_list = route_history["potential_matches"]
    if len(stops_list) <= 0:
        return

    matches_to_delete = set(matches_to_delete)
    for stop_index in matches_to_delete:
        del stops_list[stop_index]


def update_matched_stop(
    stop_index: str,
    last_time_in_zone: datetime,
    route_history: RouteHistory,
    potential_matches_to_delete: list[str],
    is_estimate: bool,  # noqa: FBT001 - boolean argument is fine for now
) -> None:
    """Update last match, matched stops with current match and remove it from the potential match list"""
    potential_matches_to_delete.append(stop_index)
    matched_stop = create_matched_stop(last_time_in_zone, is_estimate)
    route_history["matched_stops"][stop_index] = matched_stop
    logger.debug(
        f"24. moved {stop_index} to matched stops, updated matched stop stop {stop_index}: {matched_stop}",
    )


def map_matched_stop_to_db(
    is_final_stop: bool,  # noqa: FBT001 - boolean argument is fine for now
    stop: Stop,
    new_matches: list[NewDbMatch],
    stop_index: str,
    last_time_in_zone: datetime | None,
    is_estimate: bool,  # noqa: FBT001 - boolean argument is fine for now
) -> None:
    """Update new_matches with the newly matched stop which will be written to the database"""
    timetable_departure_time = stop_departure_time(stop)
    timetable_id = stop_timetable_id(stop)
    time_difference = (last_time_in_zone - timetable_departure_time).total_seconds()

    if time_difference < MATCHING_TIME_LOWER_LIMIT_IN_SECONDS:
        logger.warning(
            "This match is more than 2 hours early",
            timetable_id=timetable_id,
            time_difference=time_difference,
            last_time_in_zone=last_time_in_zone,
            timetable_departure_time=timetable_departure_time,
        )
        return
    if time_difference > MATCHING_TIME_UPPER_LIMIT_IN_SECONDS:
        logger.warning(
            "This match is more than 1 hour late",
            timetable_id=timetable_id,
            time_difference=time_difference,
            last_time_in_zone=last_time_in_zone,
            timetable_departure_time=timetable_departure_time,
        )
    # 23. update db with potential match details
    new_match: NewDbMatch = {
        "stop_index": stop_index,
        "time_difference": time_difference,
        "last_time_in_zone_str": str(last_time_in_zone.strftime("%H:%M:%S"))
        if not is_estimate
        else None,
        "timetable_id": timetable_id,
        "last_time_in_zone": last_time_in_zone if not is_estimate else None,
        "timestamp_after_estimate": last_time_in_zone if is_estimate else None,
        "otp_state": get_otp_state(is_final_stop, time_difference),
        "stop_type": "final" if is_final_stop else "Non-final",
    }
    new_matches.append(new_match)


def update_potential_match_without_recorded_at_time(
    stop_index: str,
    potential_match: PotentialMatch,
    stop_distance_in_meters: float,
) -> None:
    """Update potential match with last avl index and last distance if the current avl is outside the zone"""
    potential_match["last_distance"] = stop_distance_in_meters
    logger.debug(
        "18. updated potential match",
        stop_index=stop_index,
        potential_match=potential_match,
    )


def update_potential_match_with_recorded_at_time(
    avl: AVLRecord,
    stop_index: str,
    potential_match: PotentialMatch,
    stop_distance_in_meters: float,
) -> None:
    """Update potential match with last avl index, last distance and recorded at time if the current avl is within the zone"""
    potential_match["last_time_in_zone"] = str(avl_recorded_at_time_utc(avl))
    update_potential_match_without_recorded_at_time(
        stop_index,
        potential_match,
        stop_distance_in_meters,
    )


def select_potential_match_with_same_recordedattime(
    stop_index: str,
    route_history: RouteHistory,
    potential_matches_to_delete: list[str],
) -> str:
    selected_index = stop_index
    if stop_index in potential_matches_to_delete:
        return stop_index
    int_keys = (int(key) for key in route_history["matched_stops"])
    first_matched_stop = next(iter(sorted(int_keys)), 0)
    potential_matches = route_history["potential_matches"]
    current_recordedattime = potential_matches[stop_index]["last_time_in_zone"]
    index_with_same_recordedattime = [
        ind
        for ind, pm in potential_matches.items()
        if pm["last_time_in_zone"] == current_recordedattime
        and ind not in potential_matches_to_delete
    ]
    # 31. Is there more than 1 match being created with the same recordedattime?

    if len(index_with_same_recordedattime) <= 1:
        return selected_index

    logger.debug(
        f"{stop_index} index_with_same_recordedattime: {index_with_same_recordedattime}",
    )
    lowest_index_diff = None
    # 32. Select the stop closest to the first actual in the sequence
    for index in index_with_same_recordedattime:
        diff = int(index) - first_matched_stop
        logger.debug(f"index: {index}, diff: {diff}")
        if not lowest_index_diff or diff < lowest_index_diff:
            lowest_index_diff = diff
            selected_index = index
            continue

        if abs(int(index) - int(stop_index)) != 1:
            logger.debug(
                f"32. {stop_index} and {index} have the same recorded at time, remove {index} from potential matches",
            )
            # remove the potential match(es) that are not the closest to the first actual matched
            potential_matches_to_delete.append(index)
    return selected_index


def move_potential_match_to_match(
    route: Route,
    avl: AVLRecord,
    stop_index: str,
    potential_match: PotentialMatch,
    route_history: RouteHistory,
    potential_matches_to_delete: list[str],
    new_matches: list[NewDbMatch],
    bad_matches: list[BadDbMatch],
) -> None:
    """Move the current potential match to be a match"""
    stop = route[stop_index]
    final_stop_index = get_final_stop_index(route)
    stop_index_int = int(stop_index)
    is_final_stop = stop_index_int == final_stop_index
    matched_stops = route_history["matched_stops"]
    delete_potential_match = False
    last_time_in_zone = validate_date(potential_match["last_time_in_zone"])

    # 33. is this potential match the first match?
    if len(matched_stops) != 0:
        matched_stops_with_new_match: dict[str, MatchedStop] = {
            **matched_stops,
            stop_index: create_matched_stop(
                last_time_in_zone,
                potential_match.get("is_estimate", False),
            ),
        }
        # 20. order saved matches by recorded_at_time
        ordered_matches: dict[str, MatchedStop] = dict(
            sorted(
                matched_stops_with_new_match.items(),
                key=lambda t: validate_date(t[1]["last_match_time"]).timestamp(),
            ),
        )
        latest_index_int = int(list(ordered_matches.keys())[-1])
        highest_index_int = max(int(index) for index in matched_stops)
        lowest_index_int = min(int(index) for index in matched_stops)
        highest_index = str(highest_index_int)
        lowest_index = str(lowest_index_int)
        # check if the new match index is higher than or equal to the highest index saved
        # 21-22. is the new match index higher than the highest index saved and Will this new match be the (saved match limit + 1) actual match saved
        if (
            stop_index_int > highest_index_int
            and stop_index_int == latest_index_int
            and len(matched_stops) == SAVED_MATCHES_LIMIT
        ):
            logger.debug(
                f"{stop_index} higher than highest_matched_stop_index {highest_index}, "
                f"remove lowest matched stop from matched stops {lowest_index}",
            )
            logger.debug(
                "Matched stop identified for removal",
                stop_index=highest_index,
                matched_stop=route_history["matched_stops"][lowest_index],
            )
            # 23. Delete the lowest saved index from matched stops
            del route_history["matched_stops"][lowest_index]
        # 20. when the new match index is lower than the highest index saved
        # 28,29. Will this new match be the (saved match limit + 1) actual match saved and Is this new match the lowest index
        # 29.1 Do the two actual match index's saved have a difference of 1
        if (
            stop_index_int <= lowest_index_int
            and (
                len(matched_stops) == SAVED_MATCHES_LIMIT
                or highest_index_int - lowest_index_int == 1
            )
        ) or (
            stop_index_int > highest_index_int and stop_index_int != latest_index_int
        ):
            logger.debug(
                f"{stop_index} lower than lowest_matched_stop_index {lowest_index}, remove it from potential matches",
            )
            # 30.Delete this new potential match
            potential_matches_to_delete.append(stop_index)
            delete_potential_match = True
        #  29. It's in the middle of the matched stop sequence or there's only one matched stop
        if stop_index_int < highest_index_int and (
            stop_index_int > lowest_index_int or len(matched_stops) == 1
        ):
            # 29.2 is the last stop in the matched stops ordered by recorded_at_time the final stop of the journey?
            if latest_index_int == final_stop_index:
                logger.debug(
                    f"last matched stop in new match sequence {latest_index_int} is final stop, "
                    f"remove lowest matched stop from matched stops {lowest_index_int}",
                )
                logger.debug(
                    "Matched stop identified for removal",
                    stop_index=highest_index,
                    matched_stop=route_history["matched_stops"][lowest_index],
                )
                del route_history["matched_stops"][lowest_index]
            else:
                # 31.Delete the higher index stored from the db and json
                logger.debug(
                    f"{stop_index} lower than highest_matched_stop_index {highest_index}, "
                    f"remove matched stop index {highest_index} higher than {stop_index}",
                )
                logger.debug(
                    "Matched stop identified for removal",
                    stop_index=highest_index,
                    matched_stop=route_history["matched_stops"][highest_index],
                )
                del route_history["matched_stops"][highest_index]
                stop_details = route.get(highest_index)
                if not stop_details:
                    logger.warning(
                        f"index {highest_index} doesn't exist in timetable, group_id: {avl_group_id(avl)}",
                    )
                else:
                    bad_match: BadDbMatch = {
                        "timetable_id": stop_timetable_id(stop_details),
                    }
                    bad_matches.append(bad_match)
    if delete_potential_match:
        return

    # 24. move potential match to be a match
    is_estimate = potential_match.get("is_estimate", False)
    update_matched_stop(
        stop_index,
        last_time_in_zone,
        route_history,
        potential_matches_to_delete,
        is_estimate,
    )
    map_matched_stop_to_db(
        is_final_stop,
        stop,
        new_matches,
        stop_index,
        last_time_in_zone,
        is_estimate,
    )
    logger.debug(
        "Created matched stop from potential match",
        stop_index=stop_index,
        potential_match=potential_match,
        matched_stop=route_history["matched_stops"][stop_index],
    )


def match_avl_batch(
    timetable: TimetableStore,
    avls: Sequence[AVLRecord],
    stop_history: StopHistory,
) -> tuple[Sequence[NewDbMatch], Sequence[BadDbMatch], StopHistory]:
    """Perform matching on a batch of AVL records"""
    all_matched: list[NewDbMatch] = []
    all_removed: list[BadDbMatch] = []
    with log_execution_time(logger, "match_avl_batch", avl_count=len(avls)):
        for avl in avls:
            to_add, to_remove, stop_history = match_avl(timetable, avl, stop_history)
            # After initially matching a stop, a later avl might provide evidence that the match was incorrect.
            # Each batch should contain only a single avl for a particular journey, and we can't see future avls
            # Therefore, the caller needs to add the match, and then wipe it if we determine that in a later batch.
            all_matched.extend(to_add)
            all_removed.extend(to_remove)

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
) -> tuple[Sequence[NewDbMatch], int, int]:
    """Perform matching on all avls for a group_id"""
    if log_level:
        logger.setLevel(log_level)
    journey_matches: list[NewDbMatch] = []
    stop_history: StopHistory = {}
    for avl in avls:
        to_set, to_remove, stop_history = match_avl(timetable, avl, stop_history)
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

    no_timetable_counts = {}
    matched_routes = {}

    for avl in avls:
        group_id = avl_group_id(avl)
        stop_history_index, route = timetable.get_route(avl)
        if not route:
            key = (group_id, avl["direction_ref"])
            no_timetable_counts.setdefault(key, 0)
            no_timetable_counts[key] += 1
            continue
        matched_routes[stop_history_index] = route

    unprocessed_avls = 0
    for (group_id, direction_ref), avl_count in no_timetable_counts.items():
        logger.debug(
            "Could not find timetable for some avls",
            group_id=group_id,
            direction_ref=direction_ref,
            avl_count=avl_count,
        )
        unprocessed_avls += avl_count

    match_count = len({match["timetable_id"] for match in journey_matches})
    processed_routes = len(matched_routes)
    logger.info(
        "Processed group_id",
        expected_stop_count=sum([len(route) for route in matched_routes.values()]),
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
) -> tuple[Sequence[NewDbMatch], Sequence[BadDbMatch], StopHistory]:
    """Given an AVL, find a matching timetable and compare to expected stops, return updated stop history and database updates to perform"""
    # 1. check if group id exists in timetable
    group_id = avl_group_id(avl)
    with logger.append_context_keys(avl=avl, group_id=group_id):
        stop_history_index, route = timetable.get_route(avl)
        with logger.append_context_keys(stop_history_index=stop_history_index):
            if not route:
                logger.debug("Could not find timetable for avl in timetable extract")
                return [], [], stop_history

            logger.debug(f"stop_history_index {stop_history_index} in timetable")

            # 2. check if group id exists in stop_history, if not, create a blank group stop history
            if stop_history_index not in stop_history:
                default_route_history: RouteHistory = {
                    "last_avl_time": "",
                    "last_avl_longitude": None,
                    "last_avl_latitude": None,
                    "matched_stops": {},
                    "potential_matches": {},
                }
                stop_history[stop_history_index] = default_route_history
            route_history = stop_history[stop_history_index]
            current_avl_time = str(avl_recorded_at_time_utc(avl))

            # 3. check if current recorded_at_time is the same as the last avl time in route_history
            last_avl_time = route_history["last_avl_time"]
            if last_avl_time == current_avl_time:
                logger.debug(
                    "Same avl time seen again. Skipping avl...",
                    last_avl_time=last_avl_time,
                    current_avl_time=current_avl_time,
                )
                return [], [], stop_history

            if last_avl_time > current_avl_time:
                logger.debug(
                    "Out of order avl matching. Probably from a second vehicle",
                    last_avl_time=last_avl_time,
                    current_avl_time=current_avl_time,
                )

            bad_matches: list[BadDbMatch] = []
            # 4. update the time
            if len(route_history["matched_stops"]) > 0:
                # 6-10. Check if the bus is revisiting stop 1
                check_update_first_stop(avl, route, route_history, bad_matches)

            # 11-14. Find potential matches
            logger.debug("11. find potential matches")

            find_potential_matches(avl, route, route_history)

            # update last avl time, longitude and latitude
            route_history["last_avl_time"] = str(avl_recorded_at_time_utc(avl))
            route_history["last_avl_longitude"] = avl["longitude"]
            route_history["last_avl_latitude"] = avl["latitude"]

            # Check if avl is anywhere within the zone of a potential match
            # 14-34. Find matches
            if len(route_history.get("potential_matches")) <= 0:
                return [], bad_matches, stop_history

            new_matches: list[NewDbMatch] = []
            potential_matches_to_remove = []
            find_matches_in_potential_matches(
                avl,
                route,
                route_history,
                new_matches,
                potential_matches_to_remove,
                bad_matches,
            )
            # 22.1 remove matched stops from potential matches
            remove_matched_stops(
                route_history,
                potential_matches_to_remove,
            )

            return new_matches, bad_matches, stop_history
