import os
from datetime import UTC, datetime
from unittest import mock

import pytest

from ingestion_pipelines.sirivm_otp_matching_function.sirivm_otp_matching_function.matcher.matching import (
    check_estimated_match,
    check_update_first_stop,
    find_matches_in_potential_matches,
    find_potential_matches,
    move_potential_match_to_match,
    positions_timetable_lookup,
    remove_matched_stops,
    select_potential_match_with_same_recordedattime,
    update_matched_stop,
    update_potential_match_with_recorded_at_time,
    update_potential_match_without_recorded_at_time,
    write_matched_stop_to_db,
)
from ingestion_pipelines.sirivm_otp_matching_function.sirivm_otp_matching_function.matcher.models import (
    AVLRecord,
    EstimatedMatch,
    GroupStopHistory,
    PotentialMatch,
    RouteDetails,
    StopDetails,
    avl_group_id,
    avl_recorded_at_time_utc,
    stop_departure_time,
)

from .data.get_test_data import read_avl, read_timetable


class TestCheckUpdateFirstStop:  # noqa: D101 - BODS-7131
    avl_record = read_avl("check_update_first_stop.csv")[1]
    avl_record_5_mins = read_avl("check_update_first_stop.csv")[0]
    timetable = read_timetable("TLCT37812152024-08-20.json")
    group_id = "tlct|378|1215|2024-08-20"
    stop_pos_distances_remove_5_mins = []  # noqa: RUF012 - BODS-7131
    group_stop_history_5_mins = {  # noqa: RUF012 - BODS-7131
        "last_avl_time": str(datetime(2024, 8, 20, 11, 24, 58, tzinfo=UTC)),
        "last_avl_index": 6,
        "matched_stops": {
            "1": {
                "last_match_time": str(datetime(2024, 8, 20, 11, 23, 48, tzinfo=UTC)),
            },
        },
        "potential_matches": {
            "2": {
                "last_avl_index": 6,
                "last_distance": 58.596598093401845,
                "last_time_in_zone": str(datetime(2024, 8, 20, 11, 24, 58, tzinfo=UTC)),
            },
        },
    }
    expected_matched_stops_5_mins = {}  # noqa: RUF012 - BODS-7131
    expected_potential_matches_5_mins = {  # noqa: RUF012 - BODS-7131
        "1": {
            "last_avl_index": 8,
            "last_distance": 37.35876375439114,
            "last_time_in_zone": str(avl_recorded_at_time_utc(avl_record_5_mins)),
        },
        "2": {
            "last_avl_index": 6,
            "last_distance": 58.596598093401845,
            "last_time_in_zone": str(datetime(2024, 8, 20, 11, 24, 58, tzinfo=UTC)),
        },
    }
    expected_stop_pos_distances_remove_5_mins = [  # noqa: RUF012 - BODS-7131
        {
            "timetable_id": 893823336,
            "group_id": "tlct|378|1215|2024-08-20",
        },
    ]
    group_stop_history = {  # noqa: RUF012 - BODS-7131
        "last_avl_time": str(datetime(2024, 8, 20, 11, 34, 37, tzinfo=UTC)),
        "last_avl_index": 6,
        "matched_stops": {
            "1": {
                "last_match_time": str(datetime(2024, 8, 20, 11, 32, 5, tzinfo=UTC)),
            },
        },
        "potential_matches": {
            "2": {
                "last_avl_index": 6,
                "last_distance": 58.596598093401845,
                "last_time_in_zone": str(datetime(2024, 8, 20, 11, 34, 37, tzinfo=UTC)),
            },
        },
    }
    stop_pos_distances_remove = []  # noqa: RUF012 - BODS-7131
    expected_matched_stops = {  # noqa: RUF012 - BODS-7131
        "1": {
            "last_match_time": str(datetime(2024, 8, 20, 11, 32, 5, tzinfo=UTC)),
        },
    }
    expected_potential_matches = {  # noqa: RUF012 - BODS-7131
        "2": {
            "last_avl_index": 6,
            "last_distance": 58.596598093401845,
            "last_time_in_zone": str(datetime(2024, 8, 20, 11, 34, 37, tzinfo=UTC)),
        },
    }
    expected_stop_pos_distances_remove = []  # noqa: RUF012 - BODS-7131
    current_avl_index = 8

    def mockenv(**envvars):  # noqa: ANN003, D102 - BODS-7131
        return mock.patch.dict(os.environ, envvars)

    @mockenv(OPERATOR_REF="TLCT", LINE_NAME="378")
    @pytest.mark.parametrize(
        (
            "rec",
            "timetable_dict",
            "group_stop_history",
            "stop_pos_distances_remove",
            "current_avl_index",
            "expected_matched_stops",
            "expected_potential_matches",
            "expected_stop_pos_distances_remove",
        ),
        [
            pytest.param(
                avl_record_5_mins,
                timetable,
                group_stop_history_5_mins,
                stop_pos_distances_remove_5_mins,
                current_avl_index,
                expected_matched_stops_5_mins,
                expected_potential_matches_5_mins,
                expected_stop_pos_distances_remove_5_mins,
                id="Revisiting stop 1 within 5 mins",
            ),
            pytest.param(
                avl_record,
                timetable,
                group_stop_history,
                stop_pos_distances_remove,
                current_avl_index,
                expected_matched_stops,
                expected_potential_matches,
                expected_stop_pos_distances_remove,
                id="Revisiting stop 1 after 5 mins",
            ),
        ],
    )
    def test_check_update_first_stop_avl_within_5_mins(  # noqa: D102 - BODS-7131
        self,
        rec: AVLRecord,
        timetable_dict: dict,
        group_stop_history: dict,
        stop_pos_distances_remove: list,
        current_avl_index: int,
        expected_matched_stops: dict,
        expected_potential_matches: dict,
        expected_stop_pos_distances_remove: list,
    ):
        check_update_first_stop(
            rec,
            timetable_dict[avl_group_id(rec)],
            group_stop_history,
            stop_pos_distances_remove,
            current_avl_index,
        )
        assert group_stop_history["matched_stops"] == expected_matched_stops
        assert group_stop_history["potential_matches"] == expected_potential_matches
        assert stop_pos_distances_remove == expected_stop_pos_distances_remove


class TestFindPotentialMatches:  # noqa: D101 - BODS-7131
    avl_record = read_avl("FSRV9509052024-10-10.csv")[0]
    avl_record_2 = read_avl("FSRV9509052024-10-10.csv")[1]
    timetable = read_timetable("FSRV9509052024-10-10.json")
    route_details = timetable[avl_group_id(avl_record)]
    final_stop_index = 19
    group_stop_history = {  # noqa: RUF012 - BODS-7131
        "last_avl_index": 1,
        "last_avl_time": str(datetime(2024, 10, 10, 7, 49, 40, tzinfo=UTC)),
        "last_avl_longitude": None,
        "last_avl_latitude": None,
        "matched_stops": {},
        "potential_matches": {},
    }
    group_stop_history_2 = {  # noqa: RUF012 - BODS-7131
        "last_avl_index": 62,
        "last_avl_time": str(datetime(2024, 10, 10, 8, 25, 56, tzinfo=UTC)),
        "last_avl_longitude": None,
        "last_avl_latitude": None,
        "matched_stops": {
            "14": {
                "last_match_time": str(datetime(2024, 10, 10, 8, 25, 6, tzinfo=UTC)),
            },
        },
        "potential_matches": {},
    }

    def mockenv(**envvars):  # noqa: ANN003, D102 - BODS-7131
        return mock.patch.dict(os.environ, envvars)

    @mockenv(OPERATOR_REF="FSRV", LINE_NAME="95")
    @pytest.mark.parametrize(
        (
            "avl",
            "route_details",
            "group_stop_history",
            "current_avl_index",
            "final_stop_index",
            "expected_potential_matches",
        ),
        [
            pytest.param(
                avl_record,
                route_details,
                group_stop_history,
                1,
                final_stop_index,
                {},
                id="Drivers changing journey code early, reaching stop 15, no potential matches should be created",
            ),
            pytest.param(
                avl_record_2,
                route_details,
                group_stop_history_2,
                62,
                final_stop_index,
                {
                    "15": {
                        "last_avl_index": 62,
                        "last_distance": 13.738176401886017,
                        "last_time_in_zone": str(
                            datetime(2024, 10, 10, 8, 25, 56, tzinfo=UTC),
                        ),
                    },
                },
                id="Drivers reaching stop 15 and there's one actual match",
            ),
        ],
    )
    def test_find_potential_matches(  # noqa: D102 - BODS-7131
        self,
        avl: AVLRecord,
        route_details: RouteDetails,
        group_stop_history: GroupStopHistory,
        current_avl_index: int,
        final_stop_index: int,
        expected_potential_matches: dict[str, PotentialMatch],
    ):
        find_potential_matches(
            avl,
            route_details,
            group_stop_history,
            current_avl_index,
            final_stop_index,
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
        "last_avl_index": 30,
        "last_avl_time": str(datetime(2024, 8, 20, 11, 35, 25, tzinfo=UTC)),
        "matched_stops": {
            "4": {
                "last_match_time": str(datetime(2024, 8, 20, 11, 32, 20, tzinfo=UTC)),
            },
            "5": {
                "last_match_time": str(datetime(2024, 8, 20, 11, 32, 50, tzinfo=UTC)),
            },
        },
        "potential_matches": {
            "6": {
                "last_avl_index": 29,
                "last_distance": 142,
                "last_time_in_zone": str(datetime(2024, 8, 20, 11, 34, 42, tzinfo=UTC)),
            },
        },
    }
    group_stop_history_2 = {  # noqa: RUF012 - BODS-7131
        "last_avl_index": 90,
        "last_avl_time": str(datetime(2024, 8, 20, 11, 59, 57, tzinfo=UTC)),
        "matched_stops": {
            "42": {
                "last_match_time": str(datetime(2024, 8, 20, 11, 58, 43, tzinfo=UTC)),
            },
            "43": {
                "last_match_time": str(datetime(2024, 8, 20, 11, 59, 5, tzinfo=UTC)),
            },
        },
        "potential_matches": {
            "45": {
                "last_avl_index": 89,
                "last_distance": 11,
                "last_time_in_zone": str(datetime(2024, 8, 20, 11, 59, 57, tzinfo=UTC)),
            },
            "44": {
                "last_avl_index": 89,
                "last_distance": 13,
                "last_time_in_zone": str(datetime(2024, 8, 20, 11, 59, 27, tzinfo=UTC)),
            },
        },
    }
    group_stop_history_3 = {  # noqa: RUF012 - BODS-7131
        "last_avl_index": 91,
        "last_avl_time": str(datetime(2024, 8, 20, 12, 00, 5, tzinfo=UTC)),
        "matched_stops": {
            "43": {
                "last_match_time": str(datetime(2024, 8, 20, 11, 59, 5, tzinfo=UTC)),
            },
            "45": {
                "last_match_time": str(datetime(2024, 8, 20, 11, 59, 57, tzinfo=UTC)),
            },
        },
        "potential_matches": {
            "44": {
                "last_avl_index": 90,
                "last_distance": 332,
                "last_time_in_zone": str(datetime(2024, 8, 20, 11, 59, 27, tzinfo=UTC)),
            },
        },
    }
    group_stop_history_4 = {  # noqa: RUF012 - BODS-7131
        "last_avl_index": 77,
        "last_avl_time": str(datetime(2024, 8, 20, 11, 54, 9, tzinfo=UTC)),
        "matched_stops": {
            "34": {
                "last_match_time": str(datetime(2024, 8, 20, 11, 51, 35, tzinfo=UTC)),
            },
            "35": {
                "last_match_time": str(datetime(2024, 8, 20, 11, 53, 8, tzinfo=UTC)),
            },
        },
        "potential_matches": {
            "36": {
                "last_avl_index": 76,
                "last_distance": 8,
                "last_time_in_zone": str(datetime(2024, 8, 20, 11, 53, 43, tzinfo=UTC)),
            },
        },
    }
    group_stop_history_5 = {  # noqa: RUF012 - BODS-7131
        "last_avl_index": 2,
        "last_avl_time": str(datetime(2024, 8, 21, 7, 1, 3, tzinfo=UTC)),
        "matched_stops": {},
        "potential_matches": {
            "1": {
                "last_avl_index": 2,
                "last_distance": 11.812096582392824,
                "last_time_in_zone": str(datetime(2024, 8, 21, 7, 1, 3, tzinfo=UTC)),
            },
            "41": {
                "last_avl_index": 2,
                "last_distance": 10.812096582392824,
                "last_time_in_zone": str(datetime(2024, 8, 21, 7, 1, 34, tzinfo=UTC)),
            },
        },
    }
    group_stop_history_6 = {  # noqa: RUF012 - BODS-7131
        "last_avl_index": 101,
        "last_avl_time": str(datetime(2024, 8, 21, 7, 43, 25, tzinfo=UTC)),
        "matched_stops": {
            "40": {
                "last_match_time": str(datetime(2024, 8, 20, 7, 42, 26, tzinfo=UTC)),
            },
        },
        "potential_matches": {
            "41": {
                "last_avl_index": 101,
                "last_distance": 10.812096582392824,
                "last_time_in_zone": str(datetime(2024, 8, 21, 7, 43, 25, tzinfo=UTC)),
            },
        },
    }

    def mockenv(**envvars):  # noqa: ANN003, D102 - BODS-7131
        return mock.patch.dict(os.environ, envvars)

    @mockenv(OPERATOR_REF="TLCT", LINE_NAME="378")
    @pytest.mark.parametrize(
        (
            "avl",
            "timetable_dict",
            "group_stop_history",
            "current_avl_index",
            "stop_pos_distances",
            "potential_matches_to_delete",
            "final_stop_index",
            "stop_pos_distances_remove",
            "expected_group_stop_history",
            "expected_potential_matches_to_delete",
        ),
        [
            pytest.param(
                avl_record,
                timetable,
                group_stop_history,
                30,
                [],  # stop pos dist
                [],  # potential_matches_to_delete
                45,  # final_stop_index
                [],  # stop_pos_distances_remove,
                {
                    "last_avl_index": 30,
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
                        },
                    },
                    "potential_matches": {
                        "6": {
                            "last_avl_index": 29,
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
                90,
                [],  # stop pos dist
                [],  # potential_matches_to_delete
                45,  # final_stop_index
                [],  # stop_pos_distances_remove,
                {
                    "last_avl_index": 90,
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
                        },
                    },
                    "potential_matches": {
                        "45": {
                            "last_avl_index": 89,
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
                        },
                        "44": {
                            "last_avl_index": 90,
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
                91,
                [],  # stop pos dist
                [],  # potential_matches_to_delete
                45,  # final_stop_index
                [],  # stop_pos_distances_remove,
                {
                    "last_avl_index": 91,
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
                        },
                    },
                    "potential_matches": {
                        "44": {
                            "last_avl_index": 90,
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
                77,
                [],  # stop pos dist
                [],  # potential_matches_to_delete
                45,  # final_stop_index
                [],  # stop_pos_distances_remove,
                {
                    "last_avl_index": 77,
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
                        },
                    },
                    "potential_matches": {
                        "36": {
                            "last_avl_index": 77,
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
                2,
                [],  # stop pos dist
                [],  # potential_matches_to_delete
                41,  # final_stop_index
                [],  # stop_pos_distances_remove,
                {
                    "last_avl_index": 2,
                    "last_avl_time": str(datetime(2024, 8, 21, 7, 1, 3, tzinfo=UTC)),
                    "matched_stops": {},
                    "potential_matches": {
                        "1": {
                            "last_avl_index": 2,
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
                        },
                        "41": {
                            "last_avl_index": 2,
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
                101,
                [],  # stop pos dist
                [],  # potential_matches_to_delete
                41,  # final_stop_index
                [],  # stop_pos_distances_remove,
                {
                    "last_avl_index": 101,
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
                        },
                    },
                    "potential_matches": {
                        "41": {
                            "last_avl_index": 101,
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
        current_avl_index: int,
        stop_pos_distances: list,
        potential_matches_to_delete: list,
        final_stop_index: int,
        stop_pos_distances_remove: list,
        expected_group_stop_history: dict,
        expected_potential_matches_to_delete: list,
    ):
        find_matches_in_potential_matches(
            avl,
            timetable_dict[avl_group_id(avl)],
            group_stop_history,
            current_avl_index,
            stop_pos_distances,
            potential_matches_to_delete,
            final_stop_index,
            stop_pos_distances_remove,
        )
        assert group_stop_history == expected_group_stop_history
        assert potential_matches_to_delete == expected_potential_matches_to_delete


class TestRemoveMatchedStops:  # noqa: D101 - BODS-7131
    timetable = read_timetable("TLCT37812152024-08-20.json")
    matches_to_delete = ["2"]  # noqa: RUF012 - BODS-7131

    def test_remove_matched_stops(self):  # noqa: D102 - BODS-7131
        group_stop_history = {
            "last_avl_time": str(datetime(2024, 9, 1, 11, 34, 37)),  # noqa: DTZ001 - BODS-7131
            "last_avl_index": 6,
            "matched_stops": {
                "1": {"last_match_time": str(datetime(2024, 9, 1, 11, 32, 5))},  # noqa: DTZ001 - BODS-7131
            },
            "potential_matches": {
                "2": {
                    "last_avl_index": 6,
                    "last_distance": 58.596598093401845,
                    "last_time_in_zone": str(datetime(2024, 9, 1, 11, 34, 37)),  # noqa: DTZ001 - BODS-7131
                },
            },
        }
        expected_group_stop_history = {
            "last_avl_time": str(datetime(2024, 9, 1, 11, 34, 37)),  # noqa: DTZ001 - BODS-7131
            "last_avl_index": 6,
            "matched_stops": {
                "1": {"last_match_time": str(datetime(2024, 9, 1, 11, 32, 5))},  # noqa: DTZ001 - BODS-7131
            },
            "potential_matches": {},
        }
        remove_matched_stops(
            group_stop_history,
            self.matches_to_delete,
        )
        assert group_stop_history == expected_group_stop_history


class TestUpdateMatchedStop:  # noqa: D101 - BODS-7131
    avl_record = read_avl("TLCT37812152024-08-20.csv")[0]
    pm_index = "1"
    last_time_in_zone = datetime(2024, 9, 1, 11, 32, 5)  # noqa: DTZ001 - BODS-7131
    group_stop_history = {  # noqa: RUF012 - BODS-7131
        "last_avl_time": str(datetime(2024, 9, 1, 11, 30, 57)),  # noqa: DTZ001 - BODS-7131
        "last_avl_index": 3,
        "matched_stops": {},
        "potential_matches": {
            "1": {
                "last_avl_index": 3,
                "last_distance": 58.596598093401845,
                "last_time_in_zone": str(datetime(2024, 9, 1, 11, 30, 57)),  # noqa: DTZ001 - BODS-7131
            },
        },
    }
    potential_matches_to_delete = []  # noqa: RUF012 - BODS-7131

    def mockenv(**envvars):  # noqa: ANN003, D102 - BODS-7131
        return mock.patch.dict(os.environ, envvars)

    @mockenv(OPERATOR_REF="TLCT", LINE_NAME="378")
    def test_update_matched_stop(self):  # noqa: D102 - BODS-7131
        update_matched_stop(
            self.avl_record,
            self.pm_index,
            self.last_time_in_zone,
            self.group_stop_history,
            self.potential_matches_to_delete,
        )
        expected_group_stop_history = {
            "last_avl_time": str(datetime(2024, 9, 1, 11, 30, 57)),  # noqa: DTZ001 - BODS-7131
            "last_avl_index": 3,
            "matched_stops": {
                "1": {"last_match_time": str(datetime(2024, 9, 1, 11, 32, 5))},  # noqa: DTZ001 - BODS-7131
            },
            "potential_matches": {
                "1": {
                    "last_avl_index": 3,
                    "last_distance": 58.596598093401845,
                    "last_time_in_zone": str(datetime(2024, 9, 1, 11, 30, 57)),  # noqa: DTZ001 - BODS-7131
                },
            },
        }
        expected_potential_matches_to_delete = ["1"]
        assert self.group_stop_history == expected_group_stop_history
        assert self.potential_matches_to_delete == expected_potential_matches_to_delete


class TestWriteMatchedStopToDb:  # noqa: D101 - BODS-7131
    timetable = read_timetable("TLCT37812152024-08-20.json")
    stop_pos_distances_non_final = []  # noqa: RUF012 - BODS-7131
    stop_pos_distances_final = []  # noqa: RUF012 - BODS-7131
    operator_ref = "TLCT"
    line_name = "378"
    journey_ref = "1215"
    date_of_journey = "2024-08-20"
    group_id = f"{operator_ref}|{line_name}|{journey_ref}|{date_of_journey}".lower()
    batch_id = 123
    last_time_in_zone_non_final = datetime(2024, 8, 20, 11, 9, 5, tzinfo=UTC)
    last_time_in_zone_final = datetime(2024, 8, 20, 11, 35, 0, tzinfo=UTC)

    @pytest.mark.parametrize(
        (
            "is_final_stop",
            "timetable_dict",
            "stop_pos_distances",
            "pm_index",
            "last_time_in_zone",
            "expected_stop_pos_distances",
        ),
        [
            pytest.param(
                False,
                timetable,
                stop_pos_distances_non_final,
                "1",
                last_time_in_zone_non_final,
                [
                    {
                        "group_id": group_id,
                        "stop_index": "1",
                        "time_difference": -355.0,
                        "last_time_in_zone_str": "11:09:05",
                        "timetable_id": 893823336,
                        "batch_id": batch_id,
                        "last_time_in_zone": last_time_in_zone_non_final,
                        "otp_state": "Early",
                        "stop_type": "Non-final",
                    },
                ],
                id="Write non-final stop to db",
            ),
            pytest.param(
                True,
                timetable,
                stop_pos_distances_final,
                "45",
                last_time_in_zone_final,
                [
                    {
                        "group_id": group_id,
                        "stop_index": "45",
                        "time_difference": -420.0,
                        "last_time_in_zone_str": "11:35:00",
                        "timetable_id": 893822665,
                        "batch_id": batch_id,
                        "last_time_in_zone": last_time_in_zone_final,
                        "otp_state": "OnTime",
                        "stop_type": "final",
                    },
                ],
                id="Write final stop to db",
            ),
        ],
    )
    def test_write_matched_final_stop_to_db(  # noqa: D102 - BODS-7131
        self,
        is_final_stop: bool,  # noqa: FBT001 - BODS-7131
        timetable_dict: dict,
        stop_pos_distances: list,
        pm_index: str,
        last_time_in_zone: datetime,
        expected_stop_pos_distances: list,  # noqa: ANN401 - BODS-7131
    ):
        write_matched_stop_to_db(
            is_final_stop,
            timetable_dict[self.group_id],
            stop_pos_distances,
            {
                "operator_ref": self.operator_ref,
                "line_name": self.line_name,
                "journey_ref": self.journey_ref,
                "date_of_journey": self.date_of_journey,
                "batch_id": self.batch_id,
            },
            pm_index,
            last_time_in_zone,
        )
        assert stop_pos_distances == expected_stop_pos_distances


class TestGetTimetableDepartureTime:  # noqa: D101 - BODS-7131
    timetable = read_timetable("TLCT37812152024-08-20.json")
    group_id = "tlct|378|1215|2024-08-20"
    pm_index = "2"

    def test_get_timetable_departure_time(self):  # noqa: D102 - BODS-7131
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
    current_avl_index = 4
    expected_pm_details_w_datetime = {  # noqa: RUF012 - BODS-7131
        "last_avl_index": 4,
        "last_distance": 12.123214,
        "last_time_in_zone": str(datetime(2024, 8, 20, 11, 26, 42, tzinfo=UTC)),
    }
    expected_pm_details_wo_datetime = {  # noqa: RUF012 - BODS-7131
        "last_avl_index": 4,
        "last_distance": 72.12345678,
        "last_time_in_zone": str(datetime(2024, 8, 20, 11, 25, 57, tzinfo=UTC)),
    }

    def mockenv(**envvars):  # noqa: ANN003, D102 - BODS-7131
        return mock.patch.dict(os.environ, envvars)

    @mockenv(OPERATOR_REF="TLCT", LINE_NAME="378")
    def test_update_potential_match_w_datetime(  # noqa: D102 - BODS-7131
        self,
    ):
        pm_details = {
            "last_avl_index": 3,
            "last_distance": 58.596598093401845,
            "last_time_in_zone": str(datetime(2024, 8, 20, 11, 25, 57, tzinfo=UTC)),
        }
        update_potential_match_with_recorded_at_time(
            self.avl_record,
            self.pm_index,
            pm_details,
            self.current_avl_index,
            12.123214,
        )
        assert pm_details == self.expected_pm_details_w_datetime

    @mockenv(OPERATOR_REF="TLCT", LINE_NAME="378")
    def test_update_potential_match_wo_datetime(  # noqa: D102 - BODS-7131
        self,
    ):
        pm_details = {
            "last_avl_index": 3,
            "last_distance": 58.596598093401845,
            "last_time_in_zone": str(datetime(2024, 8, 20, 11, 25, 57, tzinfo=UTC)),
        }
        update_potential_match_without_recorded_at_time(
            self.avl_record,
            self.pm_index,
            pm_details,
            self.current_avl_index,
            72.12345678,
        )
        assert pm_details == self.expected_pm_details_wo_datetime


class TestSelectPotentialMatchWithSameRecordedattime:  # noqa: D101 - BODS-7131
    group_stop_history_same_recordedattime = {  # noqa: RUF012 - BODS-7131
        "last_avl_index": 40,
        "last_avl_time": str(datetime(2024, 8, 23, 11, 16, 14)),  # noqa: DTZ001 - BODS-7131
        "matched_stops": {
            "39": {"last_match_time": str(datetime(2024, 8, 23, 11, 14, 41))},  # noqa: DTZ001 - BODS-7131
            "3": {"last_match_time": str(datetime(2024, 8, 23, 11, 15, 5))},  # noqa: DTZ001 - BODS-7131
        },
        "potential_matches": {
            "4": {
                "last_avl_index": 40,
                "last_distance": 311.19398802530185,
                "last_time_in_zone": str(datetime(2024, 8, 23, 11, 15, 36)),  # noqa: DTZ001 - BODS-7131
            },
            "38": {
                "last_avl_index": 40,
                "last_distance": 294.4630341883636,
                "last_time_in_zone": str(datetime(2024, 8, 23, 11, 15, 36)),  # noqa: DTZ001 - BODS-7131
            },
            "5": {
                "last_avl_index": 40,
                "last_distance": 17.612857082239692,
                "last_time_in_zone": str(datetime(2024, 8, 23, 11, 16, 14)),  # noqa: DTZ001 - BODS-7131
            },
            "37": {
                "last_avl_index": 40,
                "last_distance": 18.62101754791971,
                "last_time_in_zone": str(datetime(2024, 8, 23, 11, 16)),  # noqa: DTZ001 - BODS-7131
            },
        },
    }
    group_stop_history_same_recordedattime_2 = {  # noqa: RUF012 - BODS-7131
        "last_avl_index": 40,
        "last_avl_time": str(datetime(2024, 8, 23, 11, 16, 14)),  # noqa: DTZ001 - BODS-7131
        "matched_stops": {
            "4": {"last_match_time": str(datetime(2024, 8, 23, 11, 15, 36))},  # noqa: DTZ001 - BODS-7131
            "3": {"last_match_time": str(datetime(2024, 8, 23, 11, 15, 5))},  # noqa: DTZ001 - BODS-7131
        },
        "potential_matches": {
            "38": {
                "last_avl_index": 40,
                "last_distance": 294.4630341883636,
                "last_time_in_zone": str(datetime(2024, 8, 23, 11, 15, 36)),  # noqa: DTZ001 - BODS-7131
            },
            "5": {
                "last_avl_index": 40,
                "last_distance": 17.612857082239692,
                "last_time_in_zone": str(datetime(2024, 8, 23, 11, 16, 14)),  # noqa: DTZ001 - BODS-7131
            },
            "37": {
                "last_avl_index": 40,
                "last_distance": 18.62101754791971,
                "last_time_in_zone": str(datetime(2024, 8, 23, 11, 16)),  # noqa: DTZ001 - BODS-7131
            },
        },
    }
    group_stop_history_wo_same_recordedattime = {  # noqa: RUF012 - BODS-7131
        "last_avl_index": 3,
        "last_avl_time": str(datetime(2024, 8, 23, 10, 57, 48)),  # noqa: DTZ001 - BODS-7131
        "potential_matches": {
            "1": {
                "last_avl_index": 3,
                "last_distance": 40.03840622665115,
                "last_time_in_zone": str(datetime(2024, 8, 23, 10, 57, 48)),  # noqa: DTZ001 - BODS-7131
            },
        },
        "matched_stops": {},
    }
    group_stop_history_consecutive_index_same_recordedattime = {  # noqa: RUF012 - BODS-7131
        "last_avl_index": 3,
        "last_avl_time": str(datetime(2024, 8, 23, 10, 57, 48)),  # noqa: DTZ001 - BODS-7131
        "potential_matches": {
            "2": {
                "last_avl_index": 3,
                "last_distance": 40.03840622665115,
                "last_time_in_zone": str(datetime(2024, 8, 23, 10, 57, 48)),  # noqa: DTZ001 - BODS-7131
            },
            "3": {
                "last_avl_index": 3,
                "last_distance": 23.1234325,
                "last_time_in_zone": str(datetime(2024, 8, 23, 10, 57, 48)),  # noqa: DTZ001 - BODS-7131
            },
        },
        "matched_stops": {},
    }
    avl_record = read_avl("TLCT37812152024-08-20.csv")[0]

    def mockenv(**envvars):  # noqa: ANN003, D102 - BODS-7131
        return mock.patch.dict(os.environ, envvars)

    @mockenv(OPERATOR_REF="TLCT", LINE_NAME="378")
    @pytest.mark.parametrize(
        (
            "avl_record",
            "pm_index",
            "group_stop_history",
            "potential_matches_to_delete",
            "expected_selected_index",
            "expected_potential_matches_to_delete",
        ),
        [
            pytest.param(
                avl_record,
                "4",
                group_stop_history_same_recordedattime,
                [],
                "4",
                ["38"],
                id="With more than one potential matches with the same recorded_at_time, select the index closest to the lowest_index",
            ),
            pytest.param(
                avl_record,
                "38",
                group_stop_history_same_recordedattime,
                ["4"],
                "38",
                ["4"],
                id="With more than one potential matches with the same recorded_at_time, select the index closest to the lowest_index and not in the potential matches to delete",
            ),
            pytest.param(
                avl_record,
                "38",
                group_stop_history_same_recordedattime_2,
                ["38"],
                "38",
                ["38"],
                id="Running select potential matches with the same recorded_at_time the second time with the same batch of potential matches, skip selecting the potential match index process",
            ),
            pytest.param(
                avl_record,
                "1",
                group_stop_history_wo_same_recordedattime,
                [],
                "1",
                [],
                id="No potential matches are with the same recorded_at_time, return the current potential index",
            ),
            pytest.param(
                avl_record,
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
        avl_record: AVLRecord,
        pm_index: str,
        group_stop_history: dict,
        potential_matches_to_delete: list,
        expected_selected_index: str,
        expected_potential_matches_to_delete: list,
    ):
        selected_index = select_potential_match_with_same_recordedattime(
            avl_record,
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
    timetable = read_timetable("TLCT37812152024-08-20.json")
    timetable_2 = read_timetable("COAC4116302024-10-17.json")
    timetable_3 = read_timetable("sleait110302024-10-23.json")
    group_id = "tlct|378|1215|2024-08-20"
    final_stop_index = "41"
    final_stop_index_2 = "34"
    pm_details_1 = {  # noqa: RUF012 - BODS-7131
        "last_avl_index": 3,
        "last_distance": 75.1243252308765,
        "last_time_in_zone": str(datetime(2024, 8, 20, 11, 15, 48, tzinfo=UTC)),
    }
    group_stop_history_1 = {  # noqa: RUF012 - BODS-7131
        "last_avl_index": 3,
        "last_avl_time": str(datetime(2024, 8, 20, 11, 15, 48, tzinfo=UTC)),
        "potential_matches": {
            "1": {
                "last_avl_index": 3,
                "last_distance": 75.1243252308765,
                "last_time_in_zone": str(datetime(2024, 8, 20, 11, 15, 48, tzinfo=UTC)),
            },
        },
        "matched_stops": {},
    }
    pm_details_2 = {  # noqa: RUF012 - BODS-7131
        "last_avl_index": 30,
        "last_distance": 80.65435437,
        "last_time_in_zone": str(datetime(2024, 8, 20, 11, 20, 4, tzinfo=UTC)),
    }
    group_stop_history_2 = {  # noqa: RUF012 - BODS-7131
        "last_avl_index": 30,
        "last_avl_time": str(datetime(2024, 8, 20, 11, 20, 4, tzinfo=UTC)),
        "potential_matches": {
            "3": {
                "last_avl_index": 30,
                "last_distance": 80.65435437,
                "last_time_in_zone": str(datetime(2024, 8, 20, 11, 20, 4, tzinfo=UTC)),
            },
        },
        "matched_stops": {
            "1": {
                "last_match_time": str(datetime(2024, 8, 20, 11, 15, 48, tzinfo=UTC)),
            },
            "2": {
                "last_match_time": str(datetime(2024, 8, 20, 11, 17, 6, tzinfo=UTC)),
            },
        },
    }
    pm_details_3 = {  # noqa: RUF012 - BODS-7131
        "last_avl_index": 59,
        "last_distance": 72.1232432,
        "last_time_in_zone": str(datetime(2024, 8, 20, 11, 39, 54, tzinfo=UTC)),
    }
    group_stop_history_3 = {  # noqa: RUF012 - BODS-7131
        "last_avl_index": 59,
        "last_avl_time": str(datetime(2024, 8, 20, 11, 39, 54, tzinfo=UTC)),
        "potential_matches": {
            "15": {
                "last_avl_index": 59,
                "last_distance": 72.1232432,
                "last_time_in_zone": str(datetime(2024, 8, 20, 11, 37, 54, tzinfo=UTC)),
            },
            "23": {
                "last_avl_index": 59,
                "last_distance": 15.12312678,
                "last_time_in_zone": str(datetime(2024, 8, 20, 11, 39, 54, tzinfo=UTC)),
            },
        },
        "matched_stops": {
            "21": {
                "last_match_time": str(datetime(2024, 8, 20, 11, 34, 23, tzinfo=UTC)),
            },
            "22": {
                "last_match_time": str(datetime(2024, 8, 20, 11, 35, 6, tzinfo=UTC)),
            },
        },
    }

    pm_details_4 = {  # noqa: RUF012 - BODS-7131
        "last_avl_index": 59,
        "last_distance": 81.123124167,
        "last_time_in_zone": str(datetime(2024, 8, 20, 11, 36, 54, tzinfo=UTC)),
    }
    group_stop_history_4 = {  # noqa: RUF012 - BODS-7131
        "last_avl_index": 62,
        "last_avl_time": str(datetime(2024, 8, 20, 11, 39, 54, tzinfo=UTC)),
        "potential_matches": {
            "23": {
                "last_avl_index": 59,
                "last_distance": 81.123124167,
                "last_time_in_zone": str(datetime(2024, 8, 20, 11, 36, 54, tzinfo=UTC)),
            },
        },
        "matched_stops": {
            "21": {
                "last_match_time": str(datetime(2024, 8, 20, 11, 34, 23, tzinfo=UTC)),
            },
            "24": {
                "last_match_time": str(datetime(2024, 8, 20, 11, 35, 6, tzinfo=UTC)),
            },
        },
    }

    pm_details_5 = {  # noqa: RUF012 - BODS-7131
        "last_avl_index": 6,
        "last_distance": 833.8772724535825,
        "last_time_in_zone": str(
            datetime(2024, 10, 17, 16, 12, 18, tzinfo=UTC),
        ),
    }
    group_stop_history_5 = {  # noqa: RUF012 - BODS-7131
        "last_avl_time": datetime(2024, 10, 17, 16, 15, 41, tzinfo=UTC),
        "last_avl_index": 7,
        "matched_stops": {
            "10": {
                "last_match_time": str(
                    datetime(2024, 10, 17, 16, 10, 6, tzinfo=UTC),
                ),
            },
        },
        "potential_matches": {
            "7": {
                "last_avl_index": 6,
                "last_distance": 833.8772724535825,
                "last_time_in_zone": str(
                    datetime(2024, 10, 17, 16, 12, 18, tzinfo=UTC),
                ),
            },
            "2": {
                "last_avl_index": 6,
                "last_distance": 35.482760472101006,
                "last_time_in_zone": str(
                    datetime(2024, 10, 17, 16, 14, 58, tzinfo=UTC),
                ),
            },
        },
    }

    pm_details_6 = {  # noqa: RUF012 - BODS-7131
        "last_avl_index": 90,
        "last_distance": 193.02253400101122,
        "last_time_in_zone": str(
            datetime(2024, 10, 23, 15, 39, 4, tzinfo=UTC),
        ),
    }
    group_stop_history_6 = {  # noqa: RUF012 - BODS-7131
        "last_avl_time": datetime(2024, 10, 23, 15, 39, 33, tzinfo=UTC),
        "last_avl_index": 91,
        "matched_stops": {
            "12": {
                "last_match_time": str(
                    datetime(2024, 10, 23, 15, 37, 43, tzinfo=UTC),
                ),
            },
            "13": {
                "last_match_time": str(
                    datetime(2024, 10, 23, 15, 38, 44, tzinfo=UTC),
                ),
            },
        },
        "potential_matches": {
            "11": {
                "last_avl_index": 90,
                "last_distance": 178.07106589653134,
                "last_time_in_zone": str(
                    datetime(2024, 10, 23, 15, 39, 4, tzinfo=UTC),
                ),
            },
            "12": {
                "last_avl_index": 90,
                "last_distance": 193.02253400101122,
                "last_time_in_zone": str(
                    datetime(2024, 10, 23, 15, 39, 4, tzinfo=UTC),
                ),
            },
            "14": {
                "last_avl_index": 90,
                "last_distance": 47.3828826762825,
                "last_time_in_zone": str(
                    datetime(2024, 10, 23, 15, 39, 27, tzinfo=UTC),
                ),
            },
            "15": {
                "last_avl_index": 91,
                "last_distance": 37.35516130497534,
                "last_time_in_zone": str(
                    datetime(2024, 10, 23, 15, 39, 33, tzinfo=UTC),
                ),
            },
        },
    }

    def mockenv(**envvars):  # noqa: ANN003, D102 - BODS-7131
        return mock.patch.dict(os.environ, envvars)

    @mockenv(OPERATOR_REF="TLCT", LINE_NAME="378")
    @pytest.mark.parametrize(
        (
            "final_stop_index",
            "timetable_dict",
            "avl",
            "pm_index",
            "pm_details",
            "group_stop_history",
            "potential_matches_to_delete",
            "stop_pos_distances",
            "stop_pos_distances_remove",
            "expected_potential_matches_to_delete",
            "expected_stop_pos_distances_remove",
            "expected_matched_stops",
            "expected_stop_pos_distances",
        ),
        [
            pytest.param(
                final_stop_index,
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
                    },
                },
                [
                    {
                        "group_id": group_id,
                        "stop_index": "1",
                        "time_difference": 48.0,
                        "last_time_in_zone_str": "11:15:48",
                        "timetable_id": 893823336,
                        "batch_id": avl_record["batch_id"],
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
                    },
                ],
                id="first match",
            ),
            pytest.param(
                final_stop_index,
                timetable,
                avl_record,
                "3",
                pm_details_2,
                group_stop_history_2,
                [],
                [],
                [],  # stop_pos_distances_remove
                ["3"],  # expected_potential_matches_to_delete
                [],  # expected_stop_pos_distances_remove
                {
                    "2": {
                        "last_match_time": str(
                            datetime(2024, 8, 20, 11, 17, 6, tzinfo=UTC),
                        ),
                    },
                    "3": {
                        "last_match_time": str(
                            datetime(2024, 8, 20, 11, 20, 4, tzinfo=UTC),
                        ),
                    },
                },
                [
                    {
                        "group_id": group_id,
                        "stop_index": "3",
                        "time_difference": 184.0,
                        "last_time_in_zone_str": "11:20:04",
                        "timetable_id": 893823358,
                        "batch_id": avl_record["batch_id"],
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
                    },
                ],
                id="not first match, the pm index higher than the highest match index saved and it will be the third actual match, move the potential match to be a match and remove the lowest match index from matched stops",
            ),
            pytest.param(
                final_stop_index,
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
                    },
                    "22": {
                        "last_match_time": str(
                            datetime(2024, 8, 20, 11, 35, 6, tzinfo=UTC),
                        ),
                    },
                },
                [],
                id="not first match, the pm index lower than the lowest match index saved, remove current potential match from potential matches",
            ),
            pytest.param(
                final_stop_index,
                timetable,
                avl_record,
                "23",
                pm_details_4,
                group_stop_history_4,
                [],
                [],
                [],  # stop_pos_distances_remove
                ["23"],  # expected_potential_matches_to_delete
                [
                    {"timetable_id": 893823127, "group_id": group_id},
                ],  # expected_stop_pos_distances_remove
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
                    },
                },
                [
                    {
                        "group_id": group_id,
                        "stop_index": "23",
                        "time_difference": 534.0,
                        "last_time_in_zone_str": "11:36:54",
                        "timetable_id": 893823138,
                        "batch_id": avl_record["batch_id"],
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
                    },
                ],
                id="not first match, the pm index lower than the highest match index saved and it will be the third actual match, move the potential match to be a match and delete the indices that are higher than the current potential match index in the matched stops",
            ),
            pytest.param(
                final_stop_index_2,
                timetable_2,
                avl_record_2,
                "7",
                pm_details_5,
                group_stop_history_5,
                [],
                [],
                [],  # stop_pos_distances_remove
                ["7"],  # expected_potential_matches_to_delete
                [
                    {"timetable_id": 1091293465, "group_id": "coac|41|1630|2024-10-17"},
                ],  # expected_stop_pos_distances_remove
                {
                    "7": {
                        "last_match_time": str(
                            datetime(2024, 10, 17, 16, 12, 18, tzinfo=UTC),
                        ),
                    },
                },
                [
                    {
                        "group_id": "coac|41|1630|2024-10-17",
                        "stop_index": "7",
                        "time_difference": -1375.0,
                        "last_time_in_zone_str": "16:12:18",
                        "timetable_id": 1091293263,
                        "batch_id": avl_record_2["batch_id"],
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
                    },
                ],
                id="bus going to the starting point to start the journey and matching backwards, when matching the second bus stop and there's only one actual match, delete the first matched stop",
            ),
            pytest.param(
                40,
                timetable_3,
                avl_record_3,
                "11",
                pm_details_6,
                group_stop_history_6,
                [],
                [],
                [],  # stop_pos_distances_remove
                ["11"],  # expected_potential_matches_to_delete
                [],  # expected_stop_pos_distances_remove
                {
                    "12": {
                        "last_match_time": str(
                            datetime(2024, 10, 23, 15, 37, 43, tzinfo=UTC),
                        ),
                    },
                    "13": {
                        "last_match_time": str(
                            datetime(2024, 10, 23, 15, 38, 44, tzinfo=UTC),
                        ),
                    },
                },
                [],
                id="bus going from A to B to A again, A should not be rematched",
            ),
        ],
    )
    def test_move_potential_match_to_match(  # noqa: D102 - BODS-7131
        self,
        final_stop_index: int,
        timetable_dict: dict,
        avl: AVLRecord,
        pm_index: str,
        pm_details: dict,
        group_stop_history: dict,
        potential_matches_to_delete: list,
        stop_pos_distances: list,
        stop_pos_distances_remove: list,
        expected_potential_matches_to_delete: list,
        expected_stop_pos_distances_remove: list,
        expected_matched_stops: dict,
        expected_stop_pos_distances: list,
    ):
        move_potential_match_to_match(
            final_stop_index,
            timetable_dict[avl_group_id(avl)],
            avl,
            pm_index,
            pm_details,
            group_stop_history,
            potential_matches_to_delete,
            stop_pos_distances,
            stop_pos_distances_remove,
        )
        assert potential_matches_to_delete == expected_potential_matches_to_delete
        assert stop_pos_distances_remove == expected_stop_pos_distances_remove
        assert group_stop_history["matched_stops"] == expected_matched_stops
        assert stop_pos_distances == expected_stop_pos_distances


class TestPositionsTimetableLookup:  # noqa: D101 - BODS-7131
    from .data.expected.expected_results import (
        expected_remove_coac,
        expected_remove_slea,
        expected_remove_tlct,
        expected_set_coac,
        expected_set_slea,
        expected_set_tlct,
        expected_stop_history_coac,
        expected_stop_history_slea,
        expected_stop_history_tlct,
    )

    avl_list_tlct = read_avl("TLCT37812152024-08-20.csv")
    timetable_tlct = read_timetable("TLCT37812152024-08-20.json")
    avl_list_coac = read_avl("COAC4116302024-10-17.csv")
    timetable_coac = read_timetable("COAC4116302024-10-17.json")
    avl_list_slea = read_avl("sleait110302024-10-23.csv")
    timetable_slea = read_timetable("sleait110302024-10-23.json")

    @pytest.mark.parametrize(
        (
            "timetable",
            "avl_list",
            "stop_history",
            "expected_to_set",
            "expected_to_remove",
            "expected_stop_history",
        ),
        [
            pytest.param(
                timetable_tlct,
                avl_list_tlct,
                {},
                expected_set_tlct,
                expected_remove_tlct,
                expected_stop_history_tlct,
                id="Normal route",
            ),
            pytest.param(
                timetable_coac,
                avl_list_coac,
                {},
                expected_set_coac,
                expected_remove_coac,
                expected_stop_history_coac,
                id="Bus going to starting point to start the journey and matching backwards",
            ),
            pytest.param(
                timetable_slea,
                avl_list_slea,
                {},
                expected_set_slea,
                expected_remove_slea,
                expected_stop_history_slea,
                id="Bus matching first stop and matching a much higher index next",
            ),
        ],
    )
    def test_positions_timetable_lookup(  # noqa: D102 - BODS-7131
        self,
        timetable,
        avl_list,
        stop_history,
        expected_to_set,
        expected_to_remove,
        expected_stop_history,
    ):
        stop_history = {}
        to_set_total = []
        to_remove_total = []

        for avl in avl_list:
            # Simulate invoking the lambda once per AVL for the group id
            # In practice there is only one AVL for a given group id in each batch
            to_set, to_remove, stop_history = positions_timetable_lookup(
                timetable,
                [avl],
                stop_history,
            )
            to_remove_total = [*to_remove_total, *to_remove]
            to_set_total = [*to_set_total, *to_set]

        assert to_set_total == expected_to_set
        assert to_remove_total == expected_to_remove
        assert stop_history == expected_stop_history


class TestCheckEstimatedMatches:  # noqa: D101 - BODS-7131
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
                {"last_time_in_zone": "2024-10-10T07:49:26.153817+00:00"},
                id="Line between 2 AVL points on straight road gives an estimated match",
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
                id="AVL point within stop zone does not give estimated match",
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
        ],
    )
    def test_find_estimated_matches(  # noqa: D102 - BODS-7131
        self,
        avl: AVLRecord,
        group_stop_history: GroupStopHistory,
        stop: StopDetails,
        expected_estimated_match: EstimatedMatch,
    ):
        estimated_match = check_estimated_match(avl, group_stop_history, stop)
        assert estimated_match == expected_estimated_match
