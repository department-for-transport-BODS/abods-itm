import json
import os
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from unittest import mock

from .matching import (
    distance_from_stop,
    match_avl_batch,
)
from .models import (
    AVLRecord,
    Route,
    RouteHistory,
    StopHistory,
    Timetable,
    avl_group_id,
    stop_timetable_id,
)
from .timetable_store import TimetableStore

date_of_journey = "2025-01-01"
stops = [
    ((float(i), float(i)), f"00:{i:0>2}:00", i, date_of_journey) for i in range(40)
]

route: Route = {str(index + 1): stop for index, stop in enumerate(stops)}
start_location = stops[0][0]
far_away_location = (-1, -1)
final_stop_index = str(len(route))
base_time = datetime(2025, 1, 1, 0, 0, 0, tzinfo=UTC)


def create_avl(
    time: datetime = base_time,
    location: tuple[float, float] = start_location,
) -> AVLRecord:
    return {
        "recorded_at_time": time.isoformat(),
        "latitude": location[0],
        "longitude": location[1],
        "line_name": "2a",
        "operator_ref": "TEST",
        "journey_ref": "1337",
        "direction_ref": "outbound",
        "date_of_journey": date_of_journey,
    }


def test_no_avls_does_nothing() -> None:
    to_set, to_remove, new_stop_history = run_matcher(
        {},
        [],
        {},
    )

    assert new_stop_history == {}
    assert to_remove == []
    assert to_set == []


def test_missing_timetable_does_nothing() -> None:
    avl = create_avl()
    to_set, to_remove, new_stop_history = run_matcher(
        {},
        [avl],
        {},
    )

    assert new_stop_history == {}
    assert to_remove == []
    assert to_set == []


def test_initial_avl_outside_any_stop_zone_just_adds_journey_history() -> None:
    avl = create_avl(location=far_away_location)
    group_id = avl_group_id(avl)
    to_set, to_remove, new_stop_history = run_matcher(
        {group_id: route},
        [avl],
        {},
    )

    assert new_stop_history == {
        group_id: {
            "last_avl_latitude": far_away_location[0],
            "last_avl_longitude": far_away_location[1],
            "last_avl_time": str(base_time),
            "matched_stops": {},
            "potential_matches": {},
        },
    }
    assert to_remove == []
    assert to_set == []


def test_same_avl_time_does_nothing() -> None:
    avl = create_avl(location=far_away_location)
    group_id = avl_group_id(avl)
    journey_history = {
        "last_avl_latitude": start_location[0],
        "last_avl_longitude": start_location[1],
        "last_avl_time": str(base_time),
        "matched_stops": {},
        "potential_matches": {},
    }
    to_set, to_remove, new_stop_history = run_matcher(
        {group_id: route},
        [avl],
        {group_id: journey_history},
    )

    assert new_stop_history == {group_id: journey_history}
    assert to_remove == []
    assert to_set == []


def test_within_first_stop_zone_adds_potential_match() -> None:
    avl = create_avl()
    group_id = avl_group_id(avl)
    to_set, to_remove, new_stop_history = run_matcher(
        {group_id: route},
        [avl],
        {},
    )

    assert new_stop_history == {
        group_id: {
            "last_avl_latitude": start_location[0],
            "last_avl_longitude": start_location[1],
            "last_avl_time": str(base_time),
            "matched_stops": {},
            "potential_matches": {
                "1": {
                    "is_estimate": False,
                    "last_distance": distance_from_stop(avl, route["1"]),
                    "last_time_in_zone": str(base_time),
                },
            },
        },
    }
    assert to_remove == []
    assert to_set == []


def test_avl_outside_first_stop_zone_does_not_update_first_stop_match() -> None:
    avl_time = base_time + timedelta(minutes=1)
    avl = create_avl(time=avl_time, location=far_away_location)
    group_id = avl_group_id(avl)

    journey_history = {
        "last_avl_latitude": stops[1][0][0],
        "last_avl_longitude": stops[1][0][1],
        "last_avl_time": str(base_time),
        "matched_stops": {
            "1": {
                "last_match_time": str(base_time),
                "is_estimate": False,
            },
        },
        "potential_matches": {},
    }

    to_set, to_remove, new_stop_history = run_matcher(
        {group_id: route},
        [avl],
        {group_id: journey_history},
    )
    assert new_stop_history == {
        group_id: {
            **journey_history,
            "last_avl_time": str(avl_time),
            "last_avl_latitude": -1,
            "last_avl_longitude": -1,
        },
    }
    assert to_remove == []
    assert to_set == []


def test_revisit_first_stop_removes_match_and_adds_potential_match() -> None:
    avl_time = base_time + timedelta(minutes=4, seconds=59)
    avl = create_avl(time=avl_time)
    group_id = avl_group_id(avl)

    journey_history = {
        "last_avl_latitude": stops[1][0][0],
        "last_avl_longitude": stops[1][0][1],
        "last_avl_time": str(base_time),
        "matched_stops": {
            "1": {
                "last_match_time": str(base_time),
                "is_estimate": False,
            },
        },
        "potential_matches": {},
    }
    stop_history = {group_id: journey_history}

    to_set, to_remove, new_stop_history = run_matcher(
        {group_id: route},
        [avl],
        stop_history,
    )
    assert new_stop_history == {
        **stop_history,
        group_id: {
            **journey_history,
            "last_avl_time": str(avl_time),
            "last_avl_latitude": start_location[0],
            "last_avl_longitude": start_location[1],
            "matched_stops": {},
            "potential_matches": {
                "1": {
                    "is_estimate": False,
                    "last_distance": distance_from_stop(avl, route["1"]),
                    "last_time_in_zone": str(avl_time),
                },
            },
        },
    }
    assert to_remove == [
        {"timetable_id": stop_timetable_id(route["1"])},
    ]
    assert to_set == []


def test_revisit_first_stop_adds_potential_match_but_does_not_delete_match_if_five_minutes_have_passed() -> (
    None
):
    avl_time = base_time + timedelta(minutes=5)
    avl = create_avl(time=avl_time)
    group_id = avl_group_id(avl)

    journey_history = {
        "last_avl_latitude": stops[1][0][0],
        "last_avl_longitude": stops[1][0][1],
        "last_avl_time": str(base_time),
        "matched_stops": {
            "1": {
                "last_match_time": str(base_time),
                "is_estimate": False,
            },
        },
        "potential_matches": {},
    }
    stop_history = {group_id: journey_history}

    to_set, to_remove, new_stop_history = run_matcher(
        {group_id: route},
        [avl],
        stop_history,
    )
    assert new_stop_history == {
        **stop_history,
        group_id: {
            **journey_history,
            "last_avl_time": str(avl_time),
            "last_avl_latitude": start_location[0],
            "last_avl_longitude": start_location[1],
            "potential_matches": {
                "1": {
                    "is_estimate": False,
                    "last_distance": distance_from_stop(avl, route["1"]),
                    "last_time_in_zone": str(avl_time),
                },
            },
        },
    }
    assert to_remove == []
    assert to_set == []


def test_avl_at_final_stop_does_not_produce_potential_match_when_only_one_existing_match() -> (
    None
):
    avl_time = base_time + timedelta(minutes=5)
    avl = create_avl(time=avl_time, location=stops[-1][0])
    group_id = avl_group_id(avl)

    journey_history = {
        "last_avl_latitude": stops[-1][0][0],
        "last_avl_longitude": stops[-1][0][1],
        "last_avl_time": str(base_time),
        "matched_stops": {
            "1": {
                "last_match_time": str(base_time),
                "is_estimate": False,
            },
        },
        "potential_matches": {},
    }
    stop_history = {group_id: journey_history}

    to_set, to_remove, new_stop_history = run_matcher(
        {group_id: route},
        [avl],
        stop_history,
    )
    assert new_stop_history == {
        **stop_history,
        group_id: {
            **journey_history,
            "last_avl_time": str(avl_time),
            "last_avl_latitude": stops[-1][0][0],
            "last_avl_longitude": stops[-1][0][1],
        },
    }
    assert to_remove == []
    assert to_set == []


def test_avl_at_final_stop_does_not_produce_potential_match_it_is_already_matched() -> (
    None
):
    avl_time = base_time + timedelta(minutes=5)
    avl = create_avl(time=avl_time, location=stops[-1][0])
    group_id = avl_group_id(avl)

    journey_history = {
        "last_avl_latitude": stops[-1][0][0],
        "last_avl_longitude": stops[-1][0][1],
        "last_avl_time": str(base_time),
        "matched_stops": {
            "1": {
                "last_match_time": str(base_time),
                "is_estimate": False,
            },
            "2": {
                "last_match_time": str(base_time + timedelta(minutes=1)),
                "is_estimate": False,
            },
            final_stop_index: {
                "last_match_time": str(base_time + timedelta(minutes=2)),
                "is_estimate": False,
            },
        },
        "potential_matches": {},
    }
    stop_history = {group_id: journey_history}

    to_set, to_remove, new_stop_history = run_matcher(
        {group_id: route},
        [avl],
        stop_history,
    )
    assert new_stop_history == {
        **stop_history,
        group_id: {
            **journey_history,
            "last_avl_time": str(avl_time),
            "last_avl_latitude": stops[-1][0][0],
            "last_avl_longitude": stops[-1][0][1],
        },
    }
    assert to_remove == []
    assert to_set == []


def test_avl_across_final_stop_does_not_produce_estimated_potential_match() -> None:
    avl_time = base_time + timedelta(minutes=5)
    avl_location = (stops[-1][0][0] + 0.1, stops[-1][0][1])
    avl = create_avl(time=avl_time, location=avl_location)
    group_id = avl_group_id(avl)

    journey_history = {
        "last_avl_latitude": stops[-1][0][0] - 0.1,
        "last_avl_longitude": stops[-1][0][1],
        "last_avl_time": str(base_time),
        "matched_stops": {
            "1": {
                "last_match_time": str(base_time),
                "is_estimate": False,
            },
            "2": {
                "last_match_time": str(base_time + timedelta(minutes=1)),
                "is_estimate": False,
            },
        },
        "potential_matches": {},
    }
    stop_history = {group_id: journey_history}

    to_set, to_remove, new_stop_history = run_matcher(
        {group_id: route},
        [avl],
        stop_history,
    )
    assert new_stop_history == {
        **stop_history,
        group_id: {
            **journey_history,
            "last_avl_time": str(avl_time),
            "last_avl_latitude": avl_location[0],
            "last_avl_longitude": avl_location[1],
        },
    }
    assert to_remove == []
    assert to_set == []


def test_avl_across_stop_updates_distance_if_a_potential_match_already_exists() -> None:
    avl_time = base_time + timedelta(minutes=2, seconds=30)
    # Would otherwise be an estimated potential match
    avl_location = (stops[2][0][0] + 0.001, stops[2][0][1])
    avl = create_avl(time=avl_time, location=avl_location)
    group_id = avl_group_id(avl)

    journey_history = {
        "last_avl_latitude": stops[2][0][0] - 0.001,
        "last_avl_longitude": stops[2][0][1],
        "last_avl_time": str(base_time + timedelta(minutes=2)),
        "matched_stops": {
            "1": {
                "last_match_time": str(base_time),
                "is_estimate": False,
            },
            "2": {
                "last_match_time": str(base_time + timedelta(minutes=1)),
                "is_estimate": False,
            },
        },
        "potential_matches": {
            "3": {
                "last_distance": 10,
                "last_time_in_zone": str(base_time + timedelta(minutes=2)),
                "is_estimate": True,
            },
        },
    }
    stop_history = {group_id: journey_history}

    to_set, to_remove, new_stop_history = run_matcher(
        {group_id: route},
        [avl],
        stop_history,
    )
    assert (
        new_stop_history
        == {
            **stop_history,
            group_id: {
                **journey_history,
                "last_avl_time": str(avl_time),
                "last_avl_latitude": avl_location[0],
                "last_avl_longitude": avl_location[1],
                "potential_matches": {
                    **journey_history["potential_matches"],
                    "3": {
                        **journey_history["potential_matches"]["3"],
                        "last_distance": distance_from_stop(avl, route["3"]),
                        "is_estimate": True,  # This is probably wrong and should change to False
                    },
                },
            },
        }
    )
    assert to_remove == []
    assert to_set == []


def test_avl_across_stop_does_not_produce_estimated_potential_match_if_a_match_already_exists() -> (
    None
):
    avl_time = base_time + timedelta(minutes=2, seconds=30)
    avl_location = (stops[2][0][0] + 0.001, stops[2][0][1])
    avl = create_avl(time=avl_time, location=avl_location)
    group_id = avl_group_id(avl)

    journey_history = {
        "last_avl_latitude": stops[2][0][0] - 0.001,
        "last_avl_longitude": stops[2][0][1],
        "last_avl_time": str(base_time + timedelta(minutes=2)),
        "matched_stops": {
            "1": {
                "last_match_time": str(base_time),
                "is_estimate": False,
            },
            "2": {
                "last_match_time": str(base_time + timedelta(minutes=1)),
                "is_estimate": False,
            },
            "3": {
                "last_match_time": str(base_time + timedelta(minutes=1)),
                "is_estimate": False,
            },
        },
        "potential_matches": {},
    }
    stop_history = {group_id: journey_history}

    to_set, to_remove, new_stop_history = run_matcher(
        {group_id: route},
        [avl],
        stop_history,
    )
    assert new_stop_history == {
        **stop_history,
        group_id: {
            **journey_history,
            "last_avl_time": str(avl_time),
            "last_avl_latitude": avl_location[0],
            "last_avl_longitude": avl_location[1],
        },
    }
    assert to_remove == []
    assert to_set == []


def test_avl_across_stop_adds_estimated_potential_match_if_stop_not_in_history() -> (
    None
):
    avl_time = base_time + timedelta(minutes=2, seconds=30)
    avl_location = (stops[2][0][0] + 0.001, stops[2][0][1])
    avl = create_avl(time=avl_time, location=avl_location)
    group_id = avl_group_id(avl)

    journey_history = {
        "last_avl_latitude": stops[2][0][0] - 0.001,
        "last_avl_longitude": stops[2][0][1],
        "last_avl_time": str(base_time + timedelta(minutes=2)),
        "matched_stops": {
            "1": {
                "last_match_time": str(base_time),
                "is_estimate": False,
            },
            "2": {
                "last_match_time": str(base_time + timedelta(minutes=1)),
                "is_estimate": False,
            },
        },
        "potential_matches": {},
    }
    stop_history = {group_id: journey_history}

    to_set, to_remove, new_stop_history = run_matcher(
        {group_id: route},
        [avl],
        stop_history,
    )
    assert new_stop_history == {
        **stop_history,
        group_id: {
            **journey_history,
            "last_avl_time": str(avl_time),
            "last_avl_latitude": avl_location[0],
            "last_avl_longitude": avl_location[1],
            "potential_matches": {
                **journey_history["potential_matches"],
                "3": {
                    "is_estimate": True,
                    "last_distance": distance_from_stop(avl, route["3"]),
                    # time is deterministic but not very predictable, so hardcoded
                    "last_time_in_zone": "2025-01-01T00:02:24.476909+00:00",
                },
            },
        },
    }
    assert to_remove == []
    assert to_set == []


def test_outside_first_stop_zone_updates_initial_potential_match() -> None:
    avl_time = base_time + timedelta(minutes=1)
    avl = create_avl(time=avl_time, location=far_away_location)
    group_id = avl_group_id(avl)
    journey_history = {
        "last_avl_latitude": start_location[0],
        "last_avl_longitude": start_location[1],
        "last_avl_time": str(base_time),
        "matched_stops": {},
        "potential_matches": {
            "1": {
                "is_estimate": False,
                "last_distance": 0,
                "last_time_in_zone": str(base_time),
            },
        },
    }
    to_set, to_remove, new_stop_history = run_matcher(
        {group_id: route},
        [avl],
        {group_id: journey_history},
    )

    assert new_stop_history == {
        group_id: {
            **journey_history,
            "last_avl_latitude": far_away_location[0],
            "last_avl_longitude": far_away_location[1],
            "last_avl_time": str(avl_time),
            "matched_stops": {},
            "potential_matches": {
                "1": {
                    "is_estimate": False,
                    "last_distance": distance_from_stop(avl, route["1"]),
                    "last_time_in_zone": str(base_time),
                },
            },
        },
    }
    assert to_remove == []
    assert to_set == []


def test_second_ping_inside_final_stop_zone_creates_match() -> None:
    avl_time = base_time + timedelta(minutes=1)
    avl = create_avl(time=avl_time, location=stops[-1][0])
    group_id = avl_group_id(avl)
    journey_history = {
        "last_avl_latitude": stops[-1][0][0],
        "last_avl_longitude": stops[-1][0][1],
        "last_avl_time": str(base_time),
        "matched_stops": {
            "3": {
                "is_estimate": False,
                "last_match_time": str(base_time),
            },
        },
        "potential_matches": {
            final_stop_index: {
                "is_estimate": False,
                "last_distance": 0,
                "last_time_in_zone": str(base_time),
            },
        },
    }
    to_set, to_remove, new_stop_history = run_matcher(
        {group_id: route},
        [avl],
        {group_id: journey_history},
    )

    assert new_stop_history == {
        group_id: {
            **journey_history,
            "last_avl_latitude": stops[-1][0][0],
            "last_avl_longitude": stops[-1][0][1],
            "last_avl_time": str(avl_time),
            "matched_stops": {
                **journey_history["matched_stops"],
                final_stop_index: {
                    "is_estimate": False,
                    "last_match_time": str(base_time),
                },
            },
            "potential_matches": {},
        },
    }
    assert to_remove == []
    assert to_set == [
        {
            "last_time_in_zone": base_time,
            "last_time_in_zone_str": base_time.time().isoformat(),
            "otp_state": "OnTime",
            "stop_index": final_stop_index,
            "stop_type": "final",
            "time_difference": -((len(route) - 1) * 60),
            "timestamp_after_estimate": None,
            "timetable_id": stop_timetable_id(route[final_stop_index]),
        },
    ]


def test_second_ping_inside_final_stop_zone_skips_potential_match_if_no_matches_exists() -> (
    None
):
    avl_time = base_time + timedelta(minutes=1)
    avl = create_avl(time=avl_time, location=stops[-1][0])
    group_id = avl_group_id(avl)
    journey_history = {
        "last_avl_latitude": stops[-1][0][0],
        "last_avl_longitude": stops[-1][0][1],
        "last_avl_time": str(base_time),
        "matched_stops": {},
        "potential_matches": {
            final_stop_index: {
                "is_estimate": False,
                "last_distance": 0,
                "last_time_in_zone": str(base_time),
            },
        },
    }
    to_set, to_remove, new_stop_history = run_matcher(
        {group_id: route},
        [avl],
        {group_id: journey_history},
    )

    assert new_stop_history == {
        group_id: {
            **journey_history,
            "last_avl_latitude": stops[-1][0][0],
            "last_avl_longitude": stops[-1][0][1],
            "last_avl_time": str(avl_time),
        },
    }
    assert to_remove == []
    assert to_set == []


def test_second_ping_inside_final_stop_zone_skips_potential_match_if_final_stop_already_matched() -> (
    None
):
    avl_time = base_time + timedelta(minutes=1)
    avl = create_avl(time=avl_time, location=stops[-1][0])
    group_id = avl_group_id(avl)
    journey_history = {
        "last_avl_latitude": stops[-1][0][0],
        "last_avl_longitude": stops[-1][0][1],
        "last_avl_time": str(base_time),
        "matched_stops": {
            final_stop_index: {
                "is_estimate": False,
                "last_match_time": str(base_time),
            },
        },
        "potential_matches": {
            final_stop_index: {
                "is_estimate": False,
                "last_distance": 0,
                "last_time_in_zone": str(base_time),
            },
        },
    }
    to_set, to_remove, new_stop_history = run_matcher(
        {group_id: route},
        [avl],
        {group_id: journey_history},
    )

    assert new_stop_history == {
        group_id: {
            **journey_history,
            "last_avl_latitude": stops[-1][0][0],
            "last_avl_longitude": stops[-1][0][1],
            "last_avl_time": str(avl_time),
        },
    }
    assert to_remove == []
    assert to_set == []


def test_outside_first_stop_zone_creates_match_if_potential_match_distance_is_outside_zone() -> (
    None
):
    avl_time = base_time + timedelta(minutes=2)
    avl = create_avl(time=avl_time, location=far_away_location)
    group_id = avl_group_id(avl)
    journey_history = {
        "last_avl_latitude": start_location[0],
        "last_avl_longitude": start_location[1],
        "last_avl_time": str(base_time),
        "matched_stops": {},
        "potential_matches": {
            "1": {
                "is_estimate": False,
                "last_distance": distance_from_stop(avl, route["1"])
                - 1,  # new avl must be moving away, same distance not good enough
                "last_time_in_zone": str(base_time),
            },
        },
    }
    to_set, to_remove, new_stop_history = run_matcher(
        {group_id: route},
        [avl],
        {group_id: journey_history},
    )

    assert new_stop_history == {
        group_id: {
            **journey_history,
            "last_avl_latitude": far_away_location[0],
            "last_avl_longitude": far_away_location[1],
            "last_avl_time": str(avl_time),
            "matched_stops": {
                "1": {
                    "is_estimate": False,
                    "last_match_time": str(base_time),
                },
            },
            "potential_matches": {},
        },
    }
    assert to_remove == []
    assert to_set == [
        {
            "last_time_in_zone": base_time,
            "last_time_in_zone_str": "00:00:00",
            "otp_state": "OnTime",
            "stop_index": "1",
            "stop_type": "Non-final",
            "time_difference": 0.0,  # same time as timetable
            "timestamp_after_estimate": None,
            "timetable_id": stop_timetable_id(route["1"]),
        },
    ]


def test_new_match_not_saved_to_database_when_avl_time_more_than_2_hours_before_expected() -> (
    None
):
    avl_time = base_time - timedelta(hours=2)
    avl = create_avl(time=avl_time, location=far_away_location)
    group_id = avl_group_id(avl)
    match_time = avl_time - timedelta(seconds=1)
    journey_history = {
        "last_avl_latitude": start_location[0],
        "last_avl_longitude": start_location[1],
        "last_avl_time": str(match_time),
        "matched_stops": {},
        "potential_matches": {
            "1": {
                "is_estimate": False,
                "last_distance": distance_from_stop(avl, route["1"])
                - 1,  # new avl must be moving away, same distance not good enough
                "last_time_in_zone": str(match_time),
            },
        },
    }
    to_set, to_remove, new_stop_history = run_matcher(
        {group_id: route},
        [avl],
        {group_id: journey_history},
    )

    assert new_stop_history == {
        group_id: {
            **journey_history,
            "last_avl_latitude": far_away_location[0],
            "last_avl_longitude": far_away_location[1],
            "last_avl_time": str(avl_time),
            "matched_stops": {
                "1": {
                    "is_estimate": False,
                    "last_match_time": str(match_time),
                },
            },
            "potential_matches": {},
        },
    }
    assert to_remove == []
    assert to_set == []


def test_new_match_still_saved_to_database_when_avl_time_more_than_1_hour_after_expected() -> (
    None
):
    match_time = base_time + timedelta(hours=1) + timedelta(seconds=1)
    avl_time = match_time + timedelta(seconds=1)
    avl = create_avl(time=avl_time, location=far_away_location)
    group_id = avl_group_id(avl)
    journey_history = {
        "last_avl_latitude": start_location[0],
        "last_avl_longitude": start_location[1],
        "last_avl_time": str(match_time),
        "matched_stops": {},
        "potential_matches": {
            "1": {
                "is_estimate": False,
                "last_distance": distance_from_stop(avl, route["1"])
                - 1,  # new avl must be moving away, same distance not good enough
                "last_time_in_zone": str(match_time),
            },
        },
    }
    to_set, to_remove, new_stop_history = run_matcher(
        {group_id: route},
        [avl],
        {group_id: journey_history},
    )

    assert new_stop_history == {
        group_id: {
            **journey_history,
            "last_avl_latitude": far_away_location[0],
            "last_avl_longitude": far_away_location[1],
            "last_avl_time": str(avl_time),
            "matched_stops": {
                "1": {
                    "is_estimate": False,
                    "last_match_time": str(match_time),
                },
            },
            "potential_matches": {},
        },
    }
    assert to_remove == []
    assert to_set == [
        {
            "last_time_in_zone": match_time,
            "last_time_in_zone_str": "01:00:01",
            "otp_state": "Late",
            "stop_index": "1",
            "stop_type": "Non-final",
            "time_difference": 3601.0,  # same time as timetable
            "timestamp_after_estimate": None,
            "timetable_id": stop_timetable_id(route["1"]),
        },
    ]


def test_second_ping_outside_stop_zone_creates_match_and_removes_older_match_from_history() -> (
    None
):
    avl_time = base_time + timedelta(minutes=1)
    avl_location = (3.5, 3.5)
    avl = create_avl(time=avl_time, location=avl_location)
    group_id = avl_group_id(avl)
    journey_history = {
        "last_avl_latitude": stops[2][0][0],
        "last_avl_longitude": stops[2][0][1],
        "last_avl_time": str(base_time),
        "matched_stops": {
            "1": {
                "is_estimate": False,
                "last_match_time": str(base_time),
            },
            "2": {
                "is_estimate": False,
                "last_match_time": str(base_time),
            },
        },
        "potential_matches": {
            "3": {
                "is_estimate": False,
                "last_distance": 100.0,
                "last_time_in_zone": str(base_time),
            },
        },
    }
    to_set, to_remove, new_stop_history = run_matcher(
        {group_id: route},
        [avl],
        {group_id: journey_history},
    )

    expected_matched_stops = {
        **journey_history["matched_stops"],
        "3": {
            "is_estimate": False,
            "last_match_time": str(base_time),
        },
    }
    del expected_matched_stops["1"]
    assert new_stop_history == {
        group_id: {
            **journey_history,
            "last_avl_latitude": avl_location[0],
            "last_avl_longitude": avl_location[1],
            "last_avl_time": str(avl_time),
            "matched_stops": expected_matched_stops,
            "potential_matches": {},
        },
    }
    assert to_remove == []
    assert to_set == [
        {
            "last_time_in_zone": base_time,
            "last_time_in_zone_str": base_time.time().isoformat(),
            "otp_state": "Early",
            "stop_index": "3",
            "stop_type": "Non-final",
            "time_difference": -120.0,
            "timestamp_after_estimate": None,
            "timetable_id": stop_timetable_id(route["3"]),
        },
    ]


def test_matches_produced_in_right_order_when_previous_avl_produced_two_potential_matches() -> (
    None
):
    avl_time = base_time + timedelta(minutes=2)
    avl = create_avl(time=avl_time, location=far_away_location)
    group_id = avl_group_id(avl)
    match_time = base_time + timedelta(minutes=1)
    journey_history = {
        "last_avl_latitude": start_location[0],
        "last_avl_longitude": start_location[1],
        "last_avl_time": str(match_time),
        "matched_stops": {},
        "potential_matches": {
            "38": {
                "is_estimate": False,
                "last_distance": distance_from_stop(avl, route["1"])
                - 1,  # new avl must be moving away, same distance not good enough
                "last_time_in_zone": str(match_time),
            },
            "4": {
                "is_estimate": False,
                "last_distance": distance_from_stop(avl, route["1"])
                - 1,  # new avl must be moving away, same distance not good enough
                "last_time_in_zone": str(match_time),
            },
        },
    }
    to_set, to_remove, new_stop_history = run_matcher(
        {group_id: route},
        [avl],
        {group_id: journey_history},
    )

    assert new_stop_history == {
        group_id: {
            **journey_history,
            "last_avl_latitude": far_away_location[0],
            "last_avl_longitude": far_away_location[1],
            "last_avl_time": str(avl_time),
            "matched_stops": {
                "4": {
                    "is_estimate": False,
                    "last_match_time": str(match_time),
                },
                "38": {
                    "is_estimate": False,
                    "last_match_time": str(match_time),
                },
            },
            "potential_matches": {},
        },
    }
    assert to_remove == []
    assert to_set == [
        {
            "last_time_in_zone": match_time,
            "last_time_in_zone_str": "00:01:00",
            "otp_state": "Early",
            "stop_index": "4",
            "stop_type": "Non-final",
            "time_difference": -(2 * 60.0),
            "timestamp_after_estimate": None,
            "timetable_id": stop_timetable_id(route["4"]),
        },
        {
            "last_time_in_zone": match_time,
            "last_time_in_zone_str": "00:01:00",
            "otp_state": "Early",
            "stop_index": "38",
            "stop_type": "Non-final",
            "time_difference": -(36 * 60.0),
            "timestamp_after_estimate": None,
            "timetable_id": stop_timetable_id(route["38"]),
        },
    ]


def run_matcher(
    timetable: Timetable,
    avls: Sequence[AVLRecord],
    stop_history: StopHistory,
) -> tuple[Sequence, Sequence, dict[str, RouteHistory]]:
    with mock.patch.dict(os.environ, {"ENABLE_ESTIMATED_MATCHING": "true"}):
        return match_avl_batch(
            TimetableStore(timetable),
            avls,
            json.loads(json.dumps(stop_history)),
        )
