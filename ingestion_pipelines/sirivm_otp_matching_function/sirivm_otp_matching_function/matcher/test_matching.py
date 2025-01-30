import os
from datetime import UTC, datetime, timedelta

import pytest

from .matching import (
    check_estimated_match,
    check_update_first_stop,
    find_matches_in_potential_matches,
    find_potential_matches,
    map_matched_stop_to_db,
    move_potential_match_to_match,
    remove_matched_stops,
    select_potential_match_with_same_recordedattime,
    update_matched_stop,
    update_potential_match_with_recorded_at_time,
    update_potential_match_without_recorded_at_time,
)
from .models import (
    AVLRecord,
    GroupStopHistory,
    PotentialMatch,
    RouteDetails,
    StopDetails,
    avl_group_id,
    avl_recorded_at_time_utc,
    stop_departure_time,
)
from .test_data.get_test_data import read_avl, read_timetable


class TestCheckUpdateFirstStop:  # noqa: D101 - BODS-7131
    avl_record = read_avl("check_update_first_stop.csv")[1]
    avl_record_5_mins = read_avl("check_update_first_stop.csv")[0]
    timetable = read_timetable("TLCT37812152024-08-20.json")
    group_id = "tlct|378|1215|2024-08-20"
    bad_matches_5_mins = []  # noqa: RUF012 - BODS-7131
    group_stop_history_5_mins = {  # noqa: RUF012 - BODS-7131
        "last_avl_time": str(datetime(2024, 8, 20, 11, 24, 58, tzinfo=UTC)),
        "matched_stops": {
            "1": {
                "last_match_time": str(datetime(2024, 8, 20, 11, 23, 48, tzinfo=UTC)),
                "is_estimate": False,
            },
        },
        "potential_matches": {
            "2": {
                "last_distance": 58.596598093401845,
                "last_time_in_zone": str(datetime(2024, 8, 20, 11, 24, 58, tzinfo=UTC)),
                "is_estimate": False,
            },
        },
    }
    expected_matched_stops_5_mins = {}  # noqa: RUF012 - BODS-7131
    expected_potential_matches_5_mins = {  # noqa: RUF012 - BODS-7131
        "1": {
            "last_distance": 37.35876375439114,
            "last_time_in_zone": str(avl_recorded_at_time_utc(avl_record_5_mins)),
            "is_estimate": False,
        },
        "2": {
            "last_distance": 58.596598093401845,
            "last_time_in_zone": str(datetime(2024, 8, 20, 11, 24, 58, tzinfo=UTC)),
            "is_estimate": False,
        },
    }
    expected_bad_matches_5_mins = [  # noqa: RUF012 - BODS-7131
        {
            "timetable_id": 893823336,
            "group_id": "tlct|378|1215|2024-08-20",
        },
    ]
    group_stop_history = {  # noqa: RUF012 - BODS-7131
        "last_avl_time": str(datetime(2024, 8, 20, 11, 34, 37, tzinfo=UTC)),
        "matched_stops": {
            "1": {
                "last_match_time": str(datetime(2024, 8, 20, 11, 32, 5, tzinfo=UTC)),
                "is_estimate": False,
            },
        },
        "potential_matches": {
            "2": {
                "last_distance": 58.596598093401845,
                "last_time_in_zone": str(datetime(2024, 8, 20, 11, 34, 37, tzinfo=UTC)),
                "is_estimate": False,
            },
        },
    }
    bad_matches = []  # noqa: RUF012 - BODS-7131
    expected_matched_stops = {  # noqa: RUF012 - BODS-7131
        "1": {
            "last_match_time": str(datetime(2024, 8, 20, 11, 32, 5, tzinfo=UTC)),
            "is_estimate": False,
        },
    }
    expected_potential_matches = {  # noqa: RUF012 - BODS-7131
        "2": {
            "last_distance": 58.596598093401845,
            "last_time_in_zone": str(datetime(2024, 8, 20, 11, 34, 37, tzinfo=UTC)),
            "is_estimate": False,
        },
    }
    expected_bad_matches = []  # noqa: RUF012 - BODS-7131

    @pytest.mark.parametrize(
        (
            "rec",
            "timetable_dict",
            "group_stop_history",
            "bad_matches",
            "expected_matched_stops",
            "expected_potential_matches",
            "expected_bad_matches",
        ),
        [
            pytest.param(
                avl_record_5_mins,
                timetable,
                group_stop_history_5_mins,
                bad_matches_5_mins,
                expected_matched_stops_5_mins,
                expected_potential_matches_5_mins,
                expected_bad_matches_5_mins,
                id="Revisiting stop 1 within 5 mins",
            ),
            pytest.param(
                avl_record,
                timetable,
                group_stop_history,
                bad_matches,
                expected_matched_stops,
                expected_potential_matches,
                expected_bad_matches,
                id="Revisiting stop 1 after 5 mins",
            ),
        ],
    )
    def test_check_update_first_stop_avl_within_5_mins(  # noqa: D102 - BODS-7131
        self,
        rec: AVLRecord,
        timetable_dict: dict,
        group_stop_history: dict,
        bad_matches: list,
        expected_matched_stops: dict,
        expected_potential_matches: dict,
        expected_bad_matches: list,
    ) -> None:
        check_update_first_stop(
            rec,
            timetable_dict[avl_group_id(rec)],
            group_stop_history,
            bad_matches,
        )
        assert group_stop_history["matched_stops"] == expected_matched_stops
        assert group_stop_history["potential_matches"] == expected_potential_matches
        assert bad_matches == expected_bad_matches


class TestFindPotentialMatches:  # noqa: D101 - BODS-7131
    avl_record = read_avl("FSRV9509052024-10-10.csv")[0]
    avl_record_2 = read_avl("FSRV9509052024-10-10.csv")[1]
    avl_record_scem = read_avl("scem9132024-10-31.csv")[5]
    timetable = read_timetable("FSRV9509052024-10-10.json")
    timetable_scem = read_timetable("scem9132024-10-31.json")
    route = timetable[avl_group_id(avl_record)]
    route_scem = timetable_scem[avl_group_id(avl_record_scem)]
    group_stop_history = {  # noqa: RUF012 - BODS-7131
        "last_avl_time": str(datetime(2024, 10, 10, 7, 49, 40, tzinfo=UTC)),
        "last_avl_longitude": None,
        "last_avl_latitude": None,
        "matched_stops": {},
        "potential_matches": {},
    }
    group_stop_history_2 = {  # noqa: RUF012 - BODS-7131
        "last_avl_time": str(datetime(2024, 10, 10, 8, 25, 56, tzinfo=UTC)),
        "last_avl_longitude": None,
        "last_avl_latitude": None,
        "matched_stops": {
            "13": {
                "last_match_time": str(datetime(2024, 10, 10, 8, 24, 26, tzinfo=UTC)),
                "is_estimate": False,
            },
            "14": {
                "last_match_time": str(datetime(2024, 10, 10, 8, 25, 6, tzinfo=UTC)),
                "is_estimate": False,
            },
        },
        "potential_matches": {},
    }
    group_stop_history_scem = {  # noqa: RUF012 - BODS-7131
        "last_avl_time": str(datetime(2024, 10, 31, 8, 8, 16, tzinfo=UTC)),
        "last_avl_latitude": 51.565052,
        "last_avl_longitude": -1.784906,
        "matched_stops": {
            "3": {
                "last_match_time": datetime(2024, 10, 31, 8, 6, 55, tzinfo=UTC),
                "is_estimate": False,
            },
        },
        "potential_matches": {  # noqa: RUF012 - BODS-7131
            "2": {
                "last_distance": 61.599382260785646,
                "last_time_in_zone": str(datetime(2024, 10, 31, 8, 7, 56, tzinfo=UTC)),
                "is_estimate": False,
            },
        },
    }

    @pytest.mark.parametrize(
        (
            "avl",
            "route",
            "group_stop_history",
            "expected_potential_matches",
        ),
        [
            pytest.param(
                avl_record,
                route,
                group_stop_history,
                {},
                id="Drivers changing journey code early, reaching stop 15, no potential matches should be created",
            ),
            pytest.param(
                avl_record_2,
                route,
                group_stop_history_2,
                {
                    "15": {
                        "last_distance": 13.738176401886017,
                        "last_time_in_zone": str(
                            datetime(2024, 10, 10, 8, 25, 56, tzinfo=UTC),
                        ),
                        "is_estimate": False,
                    },
                },
                id="Bus reaching stop 15 and there's one actual match",
            ),
            pytest.param(
                avl_record_scem,
                route_scem,
                group_stop_history_scem,
                {
                    "2": {
                        "last_distance": 48.83984813250945,
                        "last_time_in_zone": str(
                            datetime(2024, 10, 31, 8, 8, 16, tzinfo=UTC),
                        ),
                        "is_estimate": False,
                    },
                    "1": {
                        "last_distance": 53.71237107009338,
                        "last_time_in_zone": str(
                            datetime(2024, 10, 31, 8, 8, 16, tzinfo=UTC),
                        ),
                        "is_estimate": False,
                    },
                },
                id="Bus started early, matched with stop 3 and go back to the starting/end stop, final stop should not become a potential match",
            ),
        ],
    )
    def test_find_potential_matches(  # noqa: D102 - BODS-7131
        self,
        avl: AVLRecord,
        route: RouteDetails,
        group_stop_history: GroupStopHistory,
        expected_potential_matches: dict[str, PotentialMatch],
    ) -> None:
        find_potential_matches(
            avl,
            route,
            group_stop_history,
        )
        assert group_stop_history["potential_matches"] == expected_potential_matches


class TestFindMatchesInPotentialMatches:  # noqa: D101 - BODS-7131
    avl_record = read_avl("TLCT37812152024-08-20.csv")[73]
    avl_record_2 = read_avl("TLCT37812152024-08-20.csv")[220]
    avl_record_3 = read_avl("TLCT37812152024-08-20.csv")[222]
    avl_record_4 = read_avl("TLCT37812152024-08-20.csv")[183]
    avl_record_5 = read_avl("FSMR3507042024-08-21.csv")[0]
    avl_record_6 = read_avl("FSMR3507042024-08-21.csv")[101]
    timetable = read_timetable("TLCT37812152024-08-20.json")
    timetable_5 = read_timetable("FSMR3507042024-08-21.json")
    group_id = "tlct|378|1215|2024-08-20"
    group_id_5 = "fsmr|35|0704|2024-08-21"
    group_stop_history = {  # noqa: RUF012 - BODS-7131
        "last_avl_time": str(datetime(2024, 8, 20, 11, 35, 25, tzinfo=UTC)),
        "matched_stops": {
            "4": {
                "last_match_time": str(datetime(2024, 8, 20, 11, 32, 20, tzinfo=UTC)),
                "is_estimate": False,
            },
            "5": {
                "last_match_time": str(datetime(2024, 8, 20, 11, 32, 50, tzinfo=UTC)),
                "is_estimate": False,
            },
        },
        "potential_matches": {
            "6": {
                "last_distance": 142,
                "last_time_in_zone": str(datetime(2024, 8, 20, 11, 34, 42, tzinfo=UTC)),
                "is_estimate": False,
            },
        },
    }
    group_stop_history_2 = {  # noqa: RUF012 - BODS-7131
        "last_avl_time": str(datetime(2024, 8, 20, 11, 59, 57, tzinfo=UTC)),
        "matched_stops": {
            "42": {
                "last_match_time": str(datetime(2024, 8, 20, 11, 58, 43, tzinfo=UTC)),
                "is_estimate": False,
            },
            "43": {
                "last_match_time": str(datetime(2024, 8, 20, 11, 59, 5, tzinfo=UTC)),
                "is_estimate": False,
            },
        },
        "potential_matches": {
            "45": {
                "last_distance": 11,
                "last_time_in_zone": str(datetime(2024, 8, 20, 11, 59, 57, tzinfo=UTC)),
                "is_estimate": False,
            },
            "44": {
                "last_distance": 13,
                "last_time_in_zone": str(datetime(2024, 8, 20, 11, 59, 27, tzinfo=UTC)),
                "is_estimate": False,
            },
        },
    }
    group_stop_history_3 = {  # noqa: RUF012 - BODS-7131
        "last_avl_time": str(datetime(2024, 8, 20, 12, 00, 5, tzinfo=UTC)),
        "matched_stops": {
            "43": {
                "last_match_time": str(datetime(2024, 8, 20, 11, 59, 5, tzinfo=UTC)),
                "is_estimate": False,
            },
            "45": {
                "last_match_time": str(datetime(2024, 8, 20, 11, 59, 57, tzinfo=UTC)),
                "is_estimate": False,
            },
        },
        "potential_matches": {
            "44": {
                "last_distance": 332,
                "last_time_in_zone": str(datetime(2024, 8, 20, 11, 59, 27, tzinfo=UTC)),
                "is_estimate": False,
            },
        },
    }
    group_stop_history_4 = {  # noqa: RUF012 - BODS-7131
        "last_avl_time": str(datetime(2024, 8, 20, 11, 54, 9, tzinfo=UTC)),
        "matched_stops": {
            "34": {
                "last_match_time": str(datetime(2024, 8, 20, 11, 51, 35, tzinfo=UTC)),
                "is_estimate": False,
            },
            "35": {
                "last_match_time": str(datetime(2024, 8, 20, 11, 53, 8, tzinfo=UTC)),
                "is_estimate": False,
            },
        },
        "potential_matches": {
            "36": {
                "last_distance": 8,
                "last_time_in_zone": str(datetime(2024, 8, 20, 11, 53, 43, tzinfo=UTC)),
                "is_estimate": False,
            },
        },
    }
    group_stop_history_5 = {  # noqa: RUF012 - BODS-7131
        "last_avl_time": str(datetime(2024, 8, 21, 7, 1, 3, tzinfo=UTC)),
        "matched_stops": {},
        "potential_matches": {
            "1": {
                "last_distance": 11.812096582392824,
                "last_time_in_zone": str(datetime(2024, 8, 21, 7, 1, 3, tzinfo=UTC)),
                "is_estimate": False,
            },
            "41": {
                "last_distance": 10.812096582392824,
                "last_time_in_zone": str(datetime(2024, 8, 21, 7, 1, 34, tzinfo=UTC)),
                "is_estimate": False,
            },
        },
    }
    group_stop_history_6 = {  # noqa: RUF012 - BODS-7131
        "last_avl_time": str(datetime(2024, 8, 21, 7, 43, 25, tzinfo=UTC)),
        "matched_stops": {
            "40": {
                "last_match_time": str(datetime(2024, 8, 20, 7, 42, 26, tzinfo=UTC)),
                "is_estimate": False,
            },
        },
        "potential_matches": {
            "41": {
                "last_distance": 10.812096582392824,
                "last_time_in_zone": str(datetime(2024, 8, 21, 7, 43, 25, tzinfo=UTC)),
                "is_estimate": False,
            },
        },
    }

    @pytest.mark.parametrize(
        (
            "avl",
            "timetable_dict",
            "group_stop_history",
            "new_matches",
            "potential_matches_to_delete",
            "bad_matches",
            "expected_group_stop_history",
            "expected_potential_matches_to_delete",
        ),
        [
            pytest.param(
                avl_record,
                timetable,
                group_stop_history,
                [],  # stop pos dist
                [],  # potential_matches_to_delete
                [],  # bad_matches,
                {
                    "last_avl_time": str(datetime(2024, 8, 20, 11, 35, 25, tzinfo=UTC)),
                    "matched_stops": {
                        "5": {
                            "last_match_time": str(
                                datetime(
                                    2024,
                                    8,
                                    20,
                                    11,
                                    32,
                                    50,
                                    tzinfo=UTC,
                                ),
                            ),
                            "is_estimate": False,
                        },
                        "6": {
                            "last_match_time": str(
                                datetime(
                                    2024,
                                    8,
                                    20,
                                    11,
                                    34,
                                    42,
                                    tzinfo=UTC,
                                ),
                            ),
                            "is_estimate": False,
                        },
                    },
                    "potential_matches": {
                        "6": {
                            "last_distance": 142,
                            "last_time_in_zone": str(
                                datetime(
                                    2024,
                                    8,
                                    20,
                                    11,
                                    34,
                                    42,
                                    tzinfo=UTC,
                                ),
                            ),
                            "is_estimate": False,
                        },
                    },
                },
                ["6"],
                id="avl_pm_distance greater than last distance which is greater than threshold, move this potential match to a match",
            ),
            pytest.param(
                avl_record_2,
                timetable,
                group_stop_history_2,
                [],  # stop pos dist
                [],  # potential_matches_to_delete
                [],  # bad_matches,
                {
                    "last_avl_time": str(datetime(2024, 8, 20, 11, 59, 57, tzinfo=UTC)),
                    "matched_stops": {
                        "43": {
                            "last_match_time": str(
                                datetime(
                                    2024,
                                    8,
                                    20,
                                    11,
                                    59,
                                    5,
                                    tzinfo=UTC,
                                ),
                            ),
                            "is_estimate": False,
                        },
                        "45": {
                            "last_match_time": str(
                                datetime(
                                    2024,
                                    8,
                                    20,
                                    11,
                                    59,
                                    57,
                                    tzinfo=UTC,
                                ),
                            ),
                            "is_estimate": False,
                        },
                    },
                    "potential_matches": {
                        "45": {
                            "last_distance": 11,
                            "last_time_in_zone": str(
                                datetime(
                                    2024,
                                    8,
                                    20,
                                    11,
                                    59,
                                    57,
                                    tzinfo=UTC,
                                ),
                            ),
                            "is_estimate": False,
                        },
                        "44": {
                            "last_distance": 332.5369444168041,
                            "last_time_in_zone": str(
                                datetime(
                                    2024,
                                    8,
                                    20,
                                    11,
                                    59,
                                    27,
                                    tzinfo=UTC,
                                ),
                            ),
                            "is_estimate": False,
                        },
                    },
                },
                ["45"],
                id="pm_index is the final stop, move final stop to be a match",
            ),
            pytest.param(
                avl_record_3,
                timetable,
                group_stop_history_3,
                [],  # stop pos dist
                [],  # potential_matches_to_delete
                [],  # bad_matches,
                {
                    "last_avl_time": str(datetime(2024, 8, 20, 12, 00, 5, tzinfo=UTC)),
                    "matched_stops": {
                        "44": {
                            "last_match_time": str(
                                datetime(
                                    2024,
                                    8,
                                    20,
                                    11,
                                    59,
                                    27,
                                    tzinfo=UTC,
                                ),
                            ),
                            "is_estimate": False,
                        },
                        "45": {
                            "last_match_time": str(
                                datetime(
                                    2024,
                                    8,
                                    20,
                                    11,
                                    59,
                                    57,
                                    tzinfo=UTC,
                                ),
                            ),
                            "is_estimate": False,
                        },
                    },
                    "potential_matches": {
                        "44": {
                            "last_distance": 332,
                            "last_time_in_zone": str(
                                datetime(
                                    2024,
                                    8,
                                    20,
                                    11,
                                    59,
                                    27,
                                    tzinfo=UTC,
                                ),
                            ),
                            "is_estimate": False,
                        },
                    },
                },
                ["44"],
                id="final stop has been matched, but the ping after the last match fulfills the criteria for the previous stop to match, match previous stop",
            ),
            pytest.param(
                avl_record_4,
                timetable,
                group_stop_history_4,
                [],  # stop pos dist
                [],  # potential_matches_to_delete
                [],  # bad_matches,
                {
                    "last_avl_time": str(datetime(2024, 8, 20, 11, 54, 9, tzinfo=UTC)),
                    "matched_stops": {
                        "34": {
                            "last_match_time": str(
                                datetime(
                                    2024,
                                    8,
                                    20,
                                    11,
                                    51,
                                    35,
                                    tzinfo=UTC,
                                ),
                            ),
                            "is_estimate": False,
                        },
                        "35": {
                            "last_match_time": str(
                                datetime(
                                    2024,
                                    8,
                                    20,
                                    11,
                                    53,
                                    8,
                                    tzinfo=UTC,
                                ),
                            ),
                            "is_estimate": False,
                        },
                    },
                    "potential_matches": {
                        "36": {
                            "last_distance": 15.608686190208905,
                            "last_time_in_zone": str(
                                datetime(
                                    2024,
                                    8,
                                    20,
                                    11,
                                    54,
                                    9,
                                    tzinfo=UTC,
                                ),
                            ),
                            "is_estimate": False,
                        },
                    },
                },
                [],
                id="the potential match is not a final stop and avl_pm_distance is less than threshold, update potential match details",
            ),
            pytest.param(
                avl_record_5,
                timetable_5,
                group_stop_history_5,
                [],  # stop pos dist
                [],  # potential_matches_to_delete
                [],  # bad_matches,
                {
                    "last_avl_time": str(datetime(2024, 8, 21, 7, 1, 3, tzinfo=UTC)),
                    "matched_stops": {},
                    "potential_matches": {
                        "1": {
                            "last_distance": 11.812096582392824,
                            "last_time_in_zone": str(
                                datetime(
                                    2024,
                                    8,
                                    21,
                                    7,
                                    1,
                                    3,
                                    tzinfo=UTC,
                                ),
                            ),
                            "is_estimate": False,
                        },
                        "41": {
                            "last_distance": 10.812096582392824,
                            "last_time_in_zone": str(
                                datetime(
                                    2024,
                                    8,
                                    21,
                                    7,
                                    1,
                                    34,
                                    tzinfo=UTC,
                                ),
                            ),
                            "is_estimate": False,
                        },
                    },
                },
                [],
                id="the potential match is a final stop but there're no previous matches",
            ),
            pytest.param(
                avl_record_6,
                timetable_5,
                group_stop_history_6,
                [],  # stop pos dist
                [],  # potential_matches_to_delete
                [],  # bad_matches,
                {
                    "last_avl_time": str(datetime(2024, 8, 21, 7, 43, 25, tzinfo=UTC)),
                    "matched_stops": {
                        "40": {
                            "last_match_time": str(
                                datetime(
                                    2024,
                                    8,
                                    20,
                                    7,
                                    42,
                                    26,
                                    tzinfo=UTC,
                                ),
                            ),
                            "is_estimate": False,
                        },
                        "41": {
                            "last_match_time": str(
                                datetime(
                                    2024,
                                    8,
                                    21,
                                    7,
                                    43,
                                    25,
                                    tzinfo=UTC,
                                ),
                            ),
                            "is_estimate": False,
                        },
                    },
                    "potential_matches": {
                        "41": {
                            "last_distance": 10.812096582392824,
                            "last_time_in_zone": str(
                                datetime(
                                    2024,
                                    8,
                                    21,
                                    7,
                                    43,
                                    25,
                                    tzinfo=UTC,
                                ),
                            ),
                            "is_estimate": False,
                        },
                    },
                },
                ["41"],
                id="the potential match is a final stop but there're no previous matches",
            ),
        ],
    )
    def test_find_matches_in_potential_matches(  # noqa: D102 - BODS-7131
        self,
        avl: AVLRecord,
        timetable_dict: dict,
        group_stop_history: dict,
        new_matches: list,
        potential_matches_to_delete: list,
        bad_matches: list,
        expected_group_stop_history: dict,
        expected_potential_matches_to_delete: list,
    ) -> None:
        find_matches_in_potential_matches(
            avl,
            timetable_dict[avl_group_id(avl)],
            group_stop_history,
            new_matches,
            potential_matches_to_delete,
            bad_matches,
        )
        assert group_stop_history == expected_group_stop_history
        assert potential_matches_to_delete == expected_potential_matches_to_delete


class TestRemoveMatchedStops:  # noqa: D101 - BODS-7131
    timetable = read_timetable("TLCT37812152024-08-20.json")
    matches_to_delete = ["2"]  # noqa: RUF012 - BODS-7131

    def test_remove_matched_stops(self) -> None:  # noqa: D102 - BODS-7131
        group_stop_history = {
            "last_avl_time": str(
                datetime(2024, 9, 1, 11, 34, 37, tzinfo=UTC),
            ),
            "matched_stops": {
                "1": {
                    "last_match_time": str(datetime(2024, 9, 1, 11, 32, 5, tzinfo=UTC)),
                    "is_estimate": False,
                },
            },
            "potential_matches": {
                "2": {
                    "last_distance": 58.596598093401845,
                    "last_time_in_zone": str(
                        datetime(2024, 9, 1, 11, 34, 37, tzinfo=UTC),
                    ),
                },
            },
            "last_avl_latitude": None,
            "last_avl_longitude": None,
        }
        expected_group_stop_history = {
            "last_avl_time": str(
                datetime(2024, 9, 1, 11, 34, 37, tzinfo=UTC),
            ),
            "matched_stops": {
                "1": {
                    "last_match_time": str(datetime(2024, 9, 1, 11, 32, 5, tzinfo=UTC)),
                    "is_estimate": False,
                },
            },
            "potential_matches": {},
            "last_avl_latitude": None,
            "last_avl_longitude": None,
        }
        remove_matched_stops(
            group_stop_history,
            self.matches_to_delete,
        )
        assert group_stop_history == expected_group_stop_history


class TestUpdateMatchedStop:  # noqa: D101 - BODS-7131
    avl_record = read_avl("TLCT37812152024-08-20.csv")[0]
    pm_index = "1"
    last_time_in_zone = datetime(2024, 9, 1, 11, 32, 5, tzinfo=UTC)
    group_stop_history = {  # noqa: RUF012 - BODS-7131
        "last_avl_time": str(
            datetime(2024, 9, 1, 11, 30, 57, tzinfo=UTC),
        ),
        "matched_stops": {},
        "potential_matches": {
            "1": {
                "last_distance": 58.596598093401845,
                "last_time_in_zone": str(
                    datetime(2024, 9, 1, 11, 30, 57, tzinfo=UTC),
                ),
                "is_estimate": False,
            },
        },
        "last_avl_latitude": None,
        "last_avl_longitude": None,
    }
    potential_matches_to_delete = []  # noqa: RUF012 - BODS-7131

    def test_update_matched_stop(self) -> None:  # noqa: D102 - BODS-7131
        update_matched_stop(
            self.pm_index,
            self.last_time_in_zone,
            self.group_stop_history,
            self.potential_matches_to_delete,
            False,  # noqa: FBT003
        )
        expected_group_stop_history = {
            "last_avl_time": str(
                datetime(2024, 9, 1, 11, 30, 57, tzinfo=UTC),
            ),
            "matched_stops": {
                "1": {
                    "last_match_time": str(datetime(2024, 9, 1, 11, 32, 5, tzinfo=UTC)),
                    "is_estimate": False,
                },
            },
            "potential_matches": {
                "1": {
                    "last_distance": 58.596598093401845,
                    "last_time_in_zone": str(
                        datetime(2024, 9, 1, 11, 30, 57, tzinfo=UTC),
                    ),
                    "is_estimate": False,
                },
            },
            "last_avl_latitude": None,
            "last_avl_longitude": None,
        }
        expected_potential_matches_to_delete = ["1"]
        assert self.group_stop_history == expected_group_stop_history
        assert self.potential_matches_to_delete == expected_potential_matches_to_delete


class TestWriteMatchedStopToDb:  # noqa: D101 - BODS-7131
    timetable = read_timetable("TLCT37812152024-08-20.json")
    new_matches_non_final = []  # noqa: RUF012 - BODS-7131
    new_matches_final = []  # noqa: RUF012 - BODS-7131
    operator_ref = "TLCT"
    line_name = "378"
    journey_ref = "1215"
    date_of_journey = "2024-08-20"
    group_id = f"{operator_ref}|{line_name}|{journey_ref}|{date_of_journey}".lower()
    last_time_in_zone_non_final = datetime(2024, 8, 20, 11, 9, 5, tzinfo=UTC)
    last_time_in_zone_final = datetime(2024, 8, 20, 11, 35, 0, tzinfo=UTC)

    @pytest.mark.parametrize(
        (
            "is_final_stop",
            "timetable_dict",
            "new_matches",
            "pm_index",
            "last_time_in_zone",
            "expected_new_matches",
        ),
        [
            pytest.param(
                False,
                timetable,
                new_matches_non_final,
                "1",
                last_time_in_zone_non_final,
                [
                    {
                        "group_id": group_id,
                        "stop_index": "1",
                        "time_difference": -355.0,
                        "last_time_in_zone_str": "11:09:05",
                        "timetable_id": 893823336,
                        "last_time_in_zone": last_time_in_zone_non_final,
                        "timestamp_after_estimate": None,
                        "otp_state": "Early",
                        "stop_type": "Non-final",
                    },
                ],
                id="Write non-final stop to db",
            ),
            pytest.param(
                True,
                timetable,
                new_matches_final,
                "45",
                last_time_in_zone_final,
                [
                    {
                        "group_id": group_id,
                        "stop_index": "45",
                        "time_difference": -420.0,
                        "last_time_in_zone_str": "11:35:00",
                        "timetable_id": 893822665,
                        "last_time_in_zone": last_time_in_zone_final,
                        "timestamp_after_estimate": None,
                        "otp_state": "OnTime",
                        "stop_type": "final",
                    },
                ],
                id="Write final stop to db",
            ),
            pytest.param(
                False,
                timetable,
                [],
                "1",
                last_time_in_zone_non_final - timedelta(seconds=7234),
                [],
                id="The match has a time difference more than 2 hours early, it shouldn't be added to the new_matches",
            ),
            pytest.param(
                False,
                timetable,
                [],
                "1",
                last_time_in_zone_non_final + timedelta(seconds=4000),
                [
                    {
                        "group_id": "tlct|378|1215|2024-08-20",
                        "last_time_in_zone": datetime(
                            2024,
                            8,
                            20,
                            12,
                            15,
                            45,
                            tzinfo=UTC,
                        ),
                        "last_time_in_zone_str": "12:15:45",
                        "otp_state": "Late",
                        "stop_index": "1",
                        "stop_type": "Non-final",
                        "time_difference": 3645.0,
                        "timestamp_after_estimate": None,
                        "timetable_id": 893823336,
                    },
                ],
                id="The match has a time difference more than 1 hour late, it should still be added to the new_matches",
            ),
        ],
    )
    def test_write_matched_stop_to_db(  # noqa: D102 - BODS-7131
        self,
        is_final_stop: bool,  # noqa: FBT001 - BODS-7131
        timetable_dict: dict,
        new_matches: list,
        pm_index: str,
        last_time_in_zone: datetime,
        expected_new_matches: list,  # noqa: ANN401 - BODS-7131
    ) -> None:
        map_matched_stop_to_db(
            is_final_stop,
            timetable_dict[self.group_id],
            new_matches,
            {
                "operator_ref": self.operator_ref,
                "line_name": self.line_name,
                "journey_ref": self.journey_ref,
                "date_of_journey": self.date_of_journey,
                "direction_ref": "inbound",
                "latitude": 0,
                "longitude": 0,
                "recorded_at_time": "something random",
            },
            pm_index,
            last_time_in_zone,
            is_estimate=False,
        )
        assert new_matches == expected_new_matches


class TestGetTimetableDepartureTime:  # noqa: D101 - BODS-7131
    timetable = read_timetable("TLCT37812152024-08-20.json")
    group_id = "tlct|378|1215|2024-08-20"
    pm_index = "2"

    def test_get_timetable_departure_time(self) -> None:  # noqa: D102 - BODS-7131
        details = self.timetable[self.group_id]
        expected_timtable_departure_time = datetime(2024, 8, 20, 11, 16, 0, tzinfo=UTC)
        assert (
            stop_departure_time(details[self.pm_index])
            == expected_timtable_departure_time
        )


class TestUpdatePotentialMatch:  # noqa: D101 - BODS-7131
    avl_record = read_avl("update_potential_match.csv")[0]
    avl_record_wo_datetime = read_avl("update_potential_match.csv")[1]
    pm_index = "1"
    expected_pm_details_w_datetime = {  # noqa: RUF012 - BODS-7131
        "last_distance": 12.123214,
        "last_time_in_zone": str(datetime(2024, 8, 20, 11, 26, 42, tzinfo=UTC)),
    }
    expected_pm_details_wo_datetime = {  # noqa: RUF012 - BODS-7131
        "last_distance": 72.12345678,
        "last_time_in_zone": str(datetime(2024, 8, 20, 11, 25, 57, tzinfo=UTC)),
    }

    def test_update_potential_match_w_datetime(  # noqa: D102 - BODS-7131
        self,
    ) -> None:
        pm_details = {
            "last_distance": 58.596598093401845,
            "last_time_in_zone": str(datetime(2024, 8, 20, 11, 25, 57, tzinfo=UTC)),
        }
        update_potential_match_with_recorded_at_time(
            self.avl_record,
            self.pm_index,
            pm_details,
            12.123214,
        )
        assert pm_details == self.expected_pm_details_w_datetime

    def test_update_potential_match_wo_datetime(  # noqa: D102 - BODS-7131
        self,
    ) -> None:
        pm_details = {
            "last_distance": 58.596598093401845,
            "last_time_in_zone": str(datetime(2024, 8, 20, 11, 25, 57, tzinfo=UTC)),
        }
        update_potential_match_without_recorded_at_time(
            self.pm_index,
            pm_details,
            72.12345678,
        )
        assert pm_details == self.expected_pm_details_wo_datetime


class TestSelectPotentialMatchWithSameRecordedattime:  # noqa: D101 - BODS-7131
    group_stop_history_same_recordedattime = {  # noqa: RUF012 - BODS-7131
        "last_avl_time": str(
            datetime(2024, 8, 23, 11, 16, 14, tzinfo=UTC),
        ),
        "matched_stops": {
            "39": {
                "last_match_time": str(datetime(2024, 8, 23, 11, 14, 41, tzinfo=UTC)),
            },
            "3": {
                "last_match_time": str(datetime(2024, 8, 23, 11, 15, 5, tzinfo=UTC)),
            },
        },
        "potential_matches": {
            "4": {
                "last_distance": 311.19398802530185,
                "last_time_in_zone": str(
                    datetime(2024, 8, 23, 11, 15, 36, tzinfo=UTC),
                ),
            },
            "38": {
                "last_distance": 294.4630341883636,
                "last_time_in_zone": str(
                    datetime(2024, 8, 23, 11, 15, 36, tzinfo=UTC),
                ),
            },
            "5": {
                "last_distance": 17.612857082239692,
                "last_time_in_zone": str(
                    datetime(2024, 8, 23, 11, 16, 14, tzinfo=UTC),
                ),
            },
            "37": {
                "last_distance": 18.62101754791971,
                "last_time_in_zone": str(
                    datetime(2024, 8, 23, 11, 16, tzinfo=UTC),
                ),
            },
        },
    }
    group_stop_history_same_recordedattime_2 = {  # noqa: RUF012 - BODS-7131
        "last_avl_time": str(
            datetime(2024, 8, 23, 11, 16, 14, tzinfo=UTC),
        ),
        "matched_stops": {
            "4": {
                "last_match_time": str(datetime(2024, 8, 23, 11, 15, 36, tzinfo=UTC)),
            },
            "3": {
                "last_match_time": str(datetime(2024, 8, 23, 11, 15, 5, tzinfo=UTC)),
            },
        },
        "potential_matches": {
            "38": {
                "last_distance": 294.4630341883636,
                "last_time_in_zone": str(
                    datetime(2024, 8, 23, 11, 15, 36, tzinfo=UTC),
                ),
            },
            "5": {
                "last_distance": 17.612857082239692,
                "last_time_in_zone": str(
                    datetime(2024, 8, 23, 11, 16, 14, tzinfo=UTC),
                ),
            },
            "37": {
                "last_distance": 18.62101754791971,
                "last_time_in_zone": str(
                    datetime(2024, 8, 23, 11, 16, tzinfo=UTC),
                ),
            },
        },
    }
    group_stop_history_wo_same_recordedattime = {  # noqa: RUF012 - BODS-7131
        "last_avl_time": str(
            datetime(2024, 8, 23, 10, 57, 48, tzinfo=UTC),
        ),
        "potential_matches": {
            "1": {
                "last_distance": 40.03840622665115,
                "last_time_in_zone": str(
                    datetime(2024, 8, 23, 10, 57, 48, tzinfo=UTC),
                ),
            },
        },
        "matched_stops": {},
    }
    group_stop_history_consecutive_index_same_recordedattime = {  # noqa: RUF012 - BODS-7131
        "last_avl_time": str(
            datetime(2024, 8, 23, 10, 57, 48, tzinfo=UTC),
        ),
        "potential_matches": {
            "2": {
                "last_distance": 40.03840622665115,
                "last_time_in_zone": str(
                    datetime(2024, 8, 23, 10, 57, 48, tzinfo=UTC),
                ),
            },
            "3": {
                "last_distance": 23.1234325,
                "last_time_in_zone": str(
                    datetime(2024, 8, 23, 10, 57, 48, tzinfo=UTC),
                ),
            },
        },
        "matched_stops": {},
    }

    @pytest.mark.parametrize(
        (
            "pm_index",
            "group_stop_history",
            "potential_matches_to_delete",
            "expected_selected_index",
            "expected_potential_matches_to_delete",
        ),
        [
            pytest.param(
                "4",
                group_stop_history_same_recordedattime,
                [],
                "4",
                ["38"],
                id="With more than one potential matches with the same recorded_at_time, select the index closest to the lowest_index",
            ),
            pytest.param(
                "38",
                group_stop_history_same_recordedattime,
                ["4"],
                "38",
                ["4"],
                id="With more than one potential matches with the same recorded_at_time, select the index closest to the lowest_index and not in the potential matches to delete",
            ),
            pytest.param(
                "38",
                group_stop_history_same_recordedattime_2,
                ["38"],
                "38",
                ["38"],
                id="Running select potential matches with the same recorded_at_time the second time with the same batch of potential matches, skip selecting the potential match index process",
            ),
            pytest.param(
                "1",
                group_stop_history_wo_same_recordedattime,
                [],
                "1",
                [],
                id="No potential matches are with the same recorded_at_time, return the current potential index",
            ),
            pytest.param(
                "2",
                group_stop_history_consecutive_index_same_recordedattime,
                [],
                "2",
                [],
                id="Consecutive stop indices with the same recorded_at_time, return the current potential index, no potential match needs to be removed",
            ),
        ],
    )
    def test_select_potential_match_with_same_recordedattime(  # noqa: D102 - BODS-7131
        self,
        pm_index: str,
        group_stop_history: dict,
        potential_matches_to_delete: list,
        expected_selected_index: str,
        expected_potential_matches_to_delete: list,
    ) -> None:
        selected_index = select_potential_match_with_same_recordedattime(
            pm_index,
            group_stop_history,
            potential_matches_to_delete,
        )
        assert selected_index == expected_selected_index
        assert potential_matches_to_delete == expected_potential_matches_to_delete


class TestMovePotentialMatchToMatch:  # noqa: D101 - BODS-7131
    avl_record = read_avl("TLCT37812152024-08-20.csv")[0]
    avl_record_2 = read_avl("COAC4116302024-10-17.csv")[7]
    avl_record_3 = read_avl("sleait110302024-10-23.csv")[7]
    avl_record_4 = read_avl("scem9132024-10-31.csv")[98]
    timetable = read_timetable("TLCT37812152024-08-20.json")
    timetable_2 = read_timetable("COAC4116302024-10-17.json")
    timetable_3 = read_timetable("sleait110302024-10-23.json")
    timetable_4 = read_timetable("scem9132024-10-31.json")
    group_id = "tlct|378|1215|2024-08-20"
    pm_details_1 = {  # noqa: RUF012 - BODS-7131
        "last_distance": 75.1243252308765,
        "last_time_in_zone": str(datetime(2024, 8, 20, 11, 15, 48, tzinfo=UTC)),
        "is_estimate": False,
    }
    group_stop_history_1 = {  # noqa: RUF012 - BODS-7131
        "last_avl_time": str(datetime(2024, 8, 20, 11, 15, 48, tzinfo=UTC)),
        "potential_matches": {
            "1": {
                "last_distance": 75.1243252308765,
                "last_time_in_zone": str(datetime(2024, 8, 20, 11, 15, 48, tzinfo=UTC)),
                "is_estimate": False,
            },
        },
        "matched_stops": {},
    }
    pm_details_2 = {  # noqa: RUF012 - BODS-7131
        "last_distance": 80.65435437,
        "last_time_in_zone": str(datetime(2024, 8, 20, 11, 20, 4, tzinfo=UTC)),
        "is_estimate": False,
    }
    group_stop_history_2 = {  # noqa: RUF012 - BODS-7131
        "last_avl_time": str(datetime(2024, 8, 20, 11, 20, 4, tzinfo=UTC)),
        "potential_matches": {
            "3": {
                "last_distance": 80.65435437,
                "last_time_in_zone": str(datetime(2024, 8, 20, 11, 20, 4, tzinfo=UTC)),
                "is_estimate": False,
            },
        },
        "matched_stops": {
            "1": {
                "last_match_time": str(datetime(2024, 8, 20, 11, 15, 48, tzinfo=UTC)),
                "is_estimate": False,
            },
            "2": {
                "last_match_time": str(datetime(2024, 8, 20, 11, 17, 6, tzinfo=UTC)),
                "is_estimate": False,
            },
        },
    }
    pm_details_3 = {  # noqa: RUF012 - BODS-7131
        "last_distance": 72.1232432,
        "last_time_in_zone": str(datetime(2024, 8, 20, 11, 39, 54, tzinfo=UTC)),
        "is_estimate": False,
    }
    group_stop_history_3 = {  # noqa: RUF012 - BODS-7131
        "last_avl_time": str(datetime(2024, 8, 20, 11, 39, 54, tzinfo=UTC)),
        "potential_matches": {
            "15": {
                "last_distance": 72.1232432,
                "last_time_in_zone": str(datetime(2024, 8, 20, 11, 37, 54, tzinfo=UTC)),
                "is_estimate": False,
            },
            "23": {
                "last_distance": 15.12312678,
                "last_time_in_zone": str(datetime(2024, 8, 20, 11, 39, 54, tzinfo=UTC)),
                "is_estimate": False,
            },
        },
        "matched_stops": {
            "21": {
                "last_match_time": str(datetime(2024, 8, 20, 11, 34, 23, tzinfo=UTC)),
                "is_estimate": False,
            },
            "22": {
                "last_match_time": str(datetime(2024, 8, 20, 11, 35, 6, tzinfo=UTC)),
                "is_estimate": False,
            },
        },
    }

    pm_details_4 = {  # noqa: RUF012 - BODS-7131
        "last_distance": 81.123124167,
        "last_time_in_zone": str(datetime(2024, 8, 20, 11, 36, 54, tzinfo=UTC)),
        "is_estimate": False,
    }
    group_stop_history_4 = {  # noqa: RUF012 - BODS-7131
        "last_avl_time": str(datetime(2024, 8, 20, 11, 39, 54, tzinfo=UTC)),
        "potential_matches": {
            "23": {
                "last_distance": 81.123124167,
                "last_time_in_zone": str(datetime(2024, 8, 20, 11, 36, 54, tzinfo=UTC)),
                "is_estimate": False,
            },
        },
        "matched_stops": {
            "21": {
                "last_match_time": str(datetime(2024, 8, 20, 11, 34, 23, tzinfo=UTC)),
                "is_estimate": False,
            },
            "24": {
                "last_match_time": str(datetime(2024, 8, 20, 11, 35, 6, tzinfo=UTC)),
                "is_estimate": False,
            },
        },
    }

    pm_details_5 = {  # noqa: RUF012 - BODS-7131
        "last_distance": 833.8772724535825,
        "last_time_in_zone": str(
            datetime(2024, 10, 17, 16, 12, 18, tzinfo=UTC),
        ),
        "is_estimate": False,
    }
    group_stop_history_5 = {  # noqa: RUF012 - BODS-7131
        "last_avl_time": datetime(2024, 10, 17, 16, 15, 41, tzinfo=UTC),
        "matched_stops": {
            "10": {
                "last_match_time": str(
                    datetime(2024, 10, 17, 16, 10, 6, tzinfo=UTC),
                ),
                "is_estimate": False,
            },
        },
        "potential_matches": {
            "7": {
                "last_distance": 833.8772724535825,
                "last_time_in_zone": str(
                    datetime(2024, 10, 17, 16, 12, 18, tzinfo=UTC),
                ),
                "is_estimate": False,
            },
            "2": {
                "last_distance": 35.482760472101006,
                "last_time_in_zone": str(
                    datetime(2024, 10, 17, 16, 14, 58, tzinfo=UTC),
                ),
                "is_estimate": False,
            },
        },
    }

    pm_details_6 = {  # noqa: RUF012 - BODS-7131
        "last_distance": 193.02253400101122,
        "last_time_in_zone": str(
            datetime(2024, 10, 23, 15, 39, 4, tzinfo=UTC),
        ),
        "is_estimate": False,
    }
    group_stop_history_6 = {  # noqa: RUF012 - BODS-7131
        "last_avl_time": datetime(2024, 10, 23, 15, 39, 33, tzinfo=UTC),
        "matched_stops": {
            "12": {
                "last_match_time": str(
                    datetime(2024, 10, 23, 15, 37, 43, tzinfo=UTC),
                ),
                "is_estimate": False,
            },
            "13": {
                "last_match_time": str(
                    datetime(2024, 10, 23, 15, 38, 44, tzinfo=UTC),
                ),
                "is_estimate": False,
            },
        },
        "potential_matches": {
            "11": {
                "last_distance": 178.07106589653134,
                "last_time_in_zone": str(
                    datetime(2024, 10, 23, 15, 39, 4, tzinfo=UTC),
                ),
                "is_estimate": False,
            },
            "12": {
                "last_distance": 193.02253400101122,
                "last_time_in_zone": str(
                    datetime(2024, 10, 23, 15, 39, 4, tzinfo=UTC),
                ),
                "is_estimate": False,
            },
            "14": {
                "last_distance": 47.3828826762825,
                "last_time_in_zone": str(
                    datetime(2024, 10, 23, 15, 39, 27, tzinfo=UTC),
                ),
                "is_estimate": False,
            },
            "15": {
                "last_distance": 37.35516130497534,
                "last_time_in_zone": str(
                    datetime(2024, 10, 23, 15, 39, 33, tzinfo=UTC),
                ),
                "is_estimate": False,
            },
        },
    }
    pm_details_7 = {  # noqa: RUF012 - BODS-7131
        "last_distance": 37.80104206056258,
        "last_time_in_zone": str(datetime(2024, 10, 31, 8, 39, 3, tzinfo=UTC)),
        "is_estimate": False,
    }
    group_stop_history_7 = {  # noqa: RUF012 - BODS-7131
        "last_avl_time": str(datetime(2024, 10, 31, 8, 39, 43, tzinfo=UTC)),
        "matched_stops": {
            "3": {
                "last_match_time": str(datetime(2024, 10, 31, 8, 6, 55, tzinfo=UTC)),
                "is_estimate": False,
            },
            "71": {
                "last_match_time": str(datetime(2024, 10, 31, 8, 36, 21, tzinfo=UTC)),
                "is_estimate": False,
            },
        },
        "potential_matches": {
            "70": {
                "last_distance": 73.61235793637137,
                "last_time_in_zone": str(datetime(2024, 10, 31, 8, 39, 3, tzinfo=UTC)),
                "is_estimate": False,
            },
        },
    }

    @pytest.mark.parametrize(
        (
            "timetable_dict",
            "avl",
            "pm_index",
            "pm_details",
            "group_stop_history",
            "potential_matches_to_delete",
            "new_matches",
            "bad_matches",
            "expected_potential_matches_to_delete",
            "expected_bad_matches",
            "expected_matched_stops",
            "expected_new_matches",
        ),
        [
            pytest.param(
                timetable,
                avl_record,
                "1",
                pm_details_1,
                group_stop_history_1,
                [],
                [],
                [],  # stop pos distances remove
                ["1"],  # expected pm to delete
                [],  # expected stop pos dist remove
                {
                    "1": {
                        "last_match_time": str(
                            datetime(
                                2024,
                                8,
                                20,
                                11,
                                15,
                                48,
                                tzinfo=UTC,
                            ),
                        ),
                        "is_estimate": False,
                    },
                },
                [
                    {
                        "group_id": group_id,
                        "stop_index": "1",
                        "time_difference": 48.0,
                        "last_time_in_zone_str": "11:15:48",
                        "timetable_id": 893823336,
                        "last_time_in_zone": datetime(
                            2024,
                            8,
                            20,
                            11,
                            15,
                            48,
                            tzinfo=UTC,
                        ),
                        "otp_state": "OnTime",
                        "stop_type": "Non-final",
                        "timestamp_after_estimate": None,
                    },
                ],
                id="first match",
            ),
            pytest.param(
                timetable,
                avl_record,
                "3",
                pm_details_2,
                group_stop_history_2,
                [],
                [],
                [],  # bad_matches
                ["3"],  # expected_potential_matches_to_delete
                [],  # expected_bad_matches
                {
                    "2": {
                        "last_match_time": str(
                            datetime(2024, 8, 20, 11, 17, 6, tzinfo=UTC),
                        ),
                        "is_estimate": False,
                    },
                    "3": {
                        "last_match_time": str(
                            datetime(2024, 8, 20, 11, 20, 4, tzinfo=UTC),
                        ),
                        "is_estimate": False,
                    },
                },
                [
                    {
                        "group_id": group_id,
                        "stop_index": "3",
                        "time_difference": 184.0,
                        "last_time_in_zone_str": "11:20:04",
                        "timetable_id": 893823358,
                        "last_time_in_zone": datetime(
                            2024,
                            8,
                            20,
                            11,
                            20,
                            4,
                            tzinfo=UTC,
                        ),
                        "otp_state": "OnTime",
                        "stop_type": "Non-final",
                        "timestamp_after_estimate": None,
                    },
                ],
                id="not first match, the pm index higher than the highest match index saved and it will be the third actual match, move the potential match to be a match and remove the lowest match index from matched stops",
            ),
            pytest.param(
                timetable,
                avl_record,
                "15",
                pm_details_3,
                group_stop_history_3,
                [],
                [],
                [],
                ["15"],
                [],
                {
                    "21": {
                        "last_match_time": str(
                            datetime(
                                2024,
                                8,
                                20,
                                11,
                                34,
                                23,
                                tzinfo=UTC,
                            ),
                        ),
                        "is_estimate": False,
                    },
                    "22": {
                        "last_match_time": str(
                            datetime(2024, 8, 20, 11, 35, 6, tzinfo=UTC),
                        ),
                        "is_estimate": False,
                    },
                },
                [],
                id="not first match, the pm index lower than the lowest match index saved, remove current potential match from potential matches",
            ),
            pytest.param(
                timetable,
                avl_record,
                "23",
                pm_details_4,
                group_stop_history_4,
                [],
                [],
                [],  # bad_matches
                ["23"],  # expected_potential_matches_to_delete
                [
                    {"timetable_id": 893823127, "group_id": group_id},
                ],  # expected_bad_matches
                {
                    "21": {
                        "last_match_time": str(
                            datetime(
                                2024,
                                8,
                                20,
                                11,
                                34,
                                23,
                                tzinfo=UTC,
                            ),
                        ),
                        "is_estimate": False,
                    },
                    "23": {
                        "last_match_time": str(
                            datetime(
                                2024,
                                8,
                                20,
                                11,
                                36,
                                54,
                                tzinfo=UTC,
                            ),
                        ),
                        "is_estimate": False,
                    },
                },
                [
                    {
                        "group_id": group_id,
                        "stop_index": "23",
                        "time_difference": 534.0,
                        "last_time_in_zone_str": "11:36:54",
                        "timetable_id": 893823138,
                        "last_time_in_zone": datetime(
                            2024,
                            8,
                            20,
                            11,
                            36,
                            54,
                            tzinfo=UTC,
                        ),
                        "otp_state": "Late",
                        "stop_type": "Non-final",
                        "timestamp_after_estimate": None,
                    },
                ],
                id="not first match, the pm index lower than the highest match index saved and it will be the third actual match, move the potential match to be a match and delete the indices that are higher than the current potential match index in the matched stops",
            ),
            pytest.param(
                timetable_2,
                avl_record_2,
                "7",
                pm_details_5,
                group_stop_history_5,
                [],
                [],
                [],  # bad_matches
                ["7"],  # expected_potential_matches_to_delete
                [
                    {"timetable_id": 1091293465, "group_id": "coac|41|1630|2024-10-17"},
                ],  # expected_bad_matches
                {
                    "7": {
                        "last_match_time": str(
                            datetime(2024, 10, 17, 16, 12, 18, tzinfo=UTC),
                        ),
                        "is_estimate": False,
                    },
                },
                [
                    {
                        "group_id": "coac|41|1630|2024-10-17",
                        "stop_index": "7",
                        "time_difference": -1375.0,
                        "last_time_in_zone_str": "16:12:18",
                        "timetable_id": 1091293263,
                        "last_time_in_zone": datetime(
                            2024,
                            10,
                            17,
                            16,
                            12,
                            18,
                            tzinfo=UTC,
                        ),
                        "otp_state": "Early",
                        "stop_type": "Non-final",
                        "timestamp_after_estimate": None,
                    },
                ],
                id="bus going to the starting point to start the journey and matching backwards, when matching the second bus stop and there's only one actual match, delete the first matched stop",
            ),
            pytest.param(
                timetable_3,
                avl_record_3,
                "11",
                pm_details_6,
                group_stop_history_6,
                [],
                [],
                [],  # bad_matches
                ["11"],  # expected_potential_matches_to_delete
                [],  # expected_bad_matches
                {
                    "12": {
                        "last_match_time": str(
                            datetime(2024, 10, 23, 15, 37, 43, tzinfo=UTC),
                        ),
                        "is_estimate": False,
                    },
                    "13": {
                        "last_match_time": str(
                            datetime(2024, 10, 23, 15, 38, 44, tzinfo=UTC),
                        ),
                        "is_estimate": False,
                    },
                },
                [],
                id="bus going from A to B to A again, A should not be rematched",
            ),
            pytest.param(
                timetable_4,
                avl_record_4,
                "70",
                pm_details_7,
                group_stop_history_7,
                [],
                [],
                [],  # bad_matches
                ["70"],  # expected_potential_matches_to_delete
                [
                    {"timetable_id": 1231325785, "group_id": "scem|9|13|2024-10-31"},
                ],  # expected_bad_matches
                {
                    "3": {
                        "last_match_time": str(
                            datetime(2024, 10, 31, 8, 6, 55, tzinfo=UTC),
                        ),
                        "is_estimate": False,
                    },
                    "70": {
                        "last_match_time": str(
                            datetime(2024, 10, 31, 8, 39, 3, tzinfo=UTC),
                        ),
                        "is_estimate": False,
                    },
                },
                [
                    {
                        "group_id": "scem|9|13|2024-10-31",
                        "last_time_in_zone": datetime(
                            2024,
                            10,
                            31,
                            8,
                            39,
                            3,
                            tzinfo=UTC,
                        ),
                        "last_time_in_zone_str": "08:39:03",
                        "otp_state": "Early",
                        "stop_index": "70",
                        "stop_type": "Non-final",
                        "time_difference": -4377.0,
                        "timetable_id": 1231325656,
                        "timestamp_after_estimate": None,
                    },
                ],
                id="bus matched final stops, then non-final stop, the final stop match should be removed",
            ),
        ],
    )
    def test_move_potential_match_to_match(  # noqa: D102 - BODS-7131
        self,
        timetable_dict: dict,
        avl: AVLRecord,
        pm_index: str,
        pm_details: dict,
        group_stop_history: dict,
        potential_matches_to_delete: list,
        new_matches: list,
        bad_matches: list,
        expected_potential_matches_to_delete: list,
        expected_bad_matches: list,
        expected_matched_stops: dict,
        expected_new_matches: list,
    ) -> None:
        move_potential_match_to_match(
            timetable_dict[avl_group_id(avl)],
            avl,
            pm_index,
            pm_details,
            group_stop_history,
            potential_matches_to_delete,
            new_matches,
            bad_matches,
        )
        assert potential_matches_to_delete == expected_potential_matches_to_delete
        assert bad_matches == expected_bad_matches
        assert group_stop_history["matched_stops"] == expected_matched_stops
        assert new_matches == expected_new_matches


class TestCheckEstimatedMatches:  # noqa: D101 - BODS-7131
    os.environ["ENABLE_ESTIMATED_MATCHING"] = "true"

    @pytest.mark.parametrize(
        (
            "avl",
            "group_stop_history",
            "stop",
            "expected_estimated_match",
        ),
        [
            pytest.param(
                {
                    "longitude": -1.648382,
                    "latitude": 53.817693,
                    "recorded_at_time": str(
                        datetime(2024, 10, 10, 7, 49, 40, tzinfo=UTC),
                    ),
                },
                {
                    "last_avl_time": str(datetime(2024, 10, 10, 7, 49, 10, tzinfo=UTC)),
                    "last_avl_longitude": -1.659246,
                    "last_avl_latitude": 53.822937,
                },
                ((53.820328, -1.654394), 0),
                "2024-10-10T07:49:26.156720+00:00",
                id="Line between 2 AVL points on straight road and within time threshold gives an estimated match",
            ),
            pytest.param(
                {
                    "longitude": -1.654394,
                    "latitude": 53.820328,
                    "recorded_at_time": str(
                        datetime(2024, 10, 10, 7, 49, 40, tzinfo=UTC),
                    ),
                },
                {
                    "last_avl_time": str(datetime(2024, 10, 10, 7, 49, 10, tzinfo=UTC)),
                    "last_avl_longitude": -1.659246,
                    "last_avl_latitude": 53.822937,
                },
                ((53.820328, -1.654394), 0),
                None,
                id="Starting AVL point within stop zone does not give estimated match",
            ),
            pytest.param(
                {
                    "longitude": -1.659246,
                    "latitude": 53.822937,
                    "recorded_at_time": str(
                        datetime(2024, 10, 10, 7, 49, 40, tzinfo=UTC),
                    ),
                },
                {
                    "last_avl_time": str(datetime(2024, 10, 10, 7, 49, 10, tzinfo=UTC)),
                    "last_avl_longitude": -1.654394,
                    "last_avl_latitude": 53.820328,
                },
                ((53.820328, -1.654394), 0),
                None,
                id="Ending AVL point within stop zone does not give estimated match",
            ),
            pytest.param(
                {
                    "longitude": -1.648382,
                    "latitude": 53.817693,
                    "recorded_at_time": str(
                        datetime(2024, 10, 10, 7, 50, 40, tzinfo=UTC),
                    ),
                },
                {
                    "last_avl_time": str(datetime(2024, 10, 10, 7, 49, 10, tzinfo=UTC)),
                    "last_avl_longitude": -1.659246,
                    "last_avl_latitude": 53.822937,
                },
                ((53.820328, -1.654394), 0),
                None,
                id="Longer than threshold time between AVL stops does not give estimated match",
            ),
            pytest.param(
                {
                    "longitude": -1.648382,
                    "latitude": 52.817693,
                    "recorded_at_time": str(
                        datetime(2024, 10, 10, 7, 50, 40, tzinfo=UTC),
                    ),
                },
                {
                    "last_avl_time": str(datetime(2024, 10, 10, 7, 50, 10, tzinfo=UTC)),
                    "last_avl_longitude": -1.659246,
                    "last_avl_latitude": 54.822937,
                },
                ((53.820328, -1.654394), 0),
                None,
                id="Longer than threshold distance between AVL stops does not give estimated match",
            ),
            pytest.param(
                {
                    "longitude": -1.648382,
                    "latitude": 53.817693,
                    "recorded_at_time": str(
                        datetime(2024, 10, 10, 7, 49, 40, tzinfo=UTC),
                    ),
                },
                {
                    "last_avl_time": str(datetime(2024, 10, 10, 7, 49, 10, tzinfo=UTC)),
                    "last_avl_longitude": None,
                    "last_avl_latitude": None,
                },
                ((53.820328, -1.654394), 0),
                None,
                id="No previous AVL does not give estimated match",
            ),
            pytest.param(
                {
                    "longitude": -1.648382,
                    "latitude": 53.817693,
                    "recorded_at_time": str(
                        datetime(2024, 10, 10, 7, 49, 40, tzinfo=UTC),
                    ),
                },
                {
                    "last_avl_time": str(datetime(2024, 10, 10, 7, 49, 10, tzinfo=UTC)),
                },
                ((53.820328, -1.654394), 0),
                None,
                id="Missing required keys does not give estimated match and does not throw error",
            ),
            pytest.param(
                {
                    "longitude": -1.648382,
                    "latitude": 53.817693,
                    "recorded_at_time": str(
                        datetime(2024, 10, 10, 7, 49, 40, tzinfo=UTC),
                    ),
                },
                {
                    "last_avl_time": str(datetime(2024, 10, 10, 7, 49, 10, tzinfo=UTC)),
                    "last_avl_longitude": -1.648382,
                    "last_avl_latitude": 53.817693,
                },
                ((53.820328, -1.654394), 0),
                None,
                id="Same starting and ending AVL points gives no estimated match",
            ),
        ],
    )
    def test_find_estimated_matches(  # noqa: D102 - BODS-7131
        self,
        avl: AVLRecord,
        group_stop_history: GroupStopHistory,
        stop: StopDetails,
        expected_estimated_match: str,
    ) -> None:
        estimated_match = check_estimated_match(avl, group_stop_history, stop)
        assert estimated_match == expected_estimated_match
