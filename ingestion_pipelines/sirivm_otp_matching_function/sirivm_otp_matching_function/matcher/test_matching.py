from datetime import UTC, datetime

import pytest

from .matching import (
    move_potential_match_to_match,
    select_potential_match_with_same_recordedattime,
)
from .models import AVLRecord, avl_group_id
from .test_data.get_test_data import read_avl, read_timetable


class TestSelectPotentialMatchWithSameRecordedattime:  # noqa: D101 - BODS-7131
    route_history_same_recordedattime = {  # noqa: RUF012 - BODS-7131
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
    route_history_same_recordedattime_2 = {  # noqa: RUF012 - BODS-7131
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
    route_history_wo_same_recordedattime = {  # noqa: RUF012 - BODS-7131
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
    route_history_consecutive_index_same_recordedattime = {  # noqa: RUF012 - BODS-7131
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
            "route_history",
            "potential_matches_to_delete",
            "expected_selected_index",
            "expected_potential_matches_to_delete",
        ),
        [
            pytest.param(
                "4",
                route_history_same_recordedattime,
                [],
                "4",
                ["38"],
                id="With more than one potential matches with the same recorded_at_time, "
                "select the index closest to the lowest_index",
            ),
            pytest.param(
                "38",
                route_history_same_recordedattime,
                ["4"],
                "38",
                ["4"],
                id="With more than one potential matches with the same recorded_at_time, "
                "select the index closest to the lowest_index and not in the potential matches to delete",
            ),
            pytest.param(
                "38",
                route_history_same_recordedattime_2,
                ["38"],
                "38",
                ["38"],
                id="Running select potential matches with the same recorded_at_time the second time "
                "with the same batch of potential matches, skip selecting the potential match index process",
            ),
            pytest.param(
                "1",
                route_history_wo_same_recordedattime,
                [],
                "1",
                [],
                id="No potential matches are with the same recorded_at_time, return the current potential index",
            ),
            pytest.param(
                "2",
                route_history_consecutive_index_same_recordedattime,
                [],
                "2",
                [],
                id="Consecutive stop indices with the same recorded_at_time, return the current potential index, "
                "no potential match needs to be removed",
            ),
        ],
    )
    def test_select_potential_match_with_same_recordedattime(  # noqa: D102 - BODS-7131
        self,
        pm_index: str,
        route_history: dict,
        potential_matches_to_delete: list,
        expected_selected_index: str,
        expected_potential_matches_to_delete: list,
    ) -> None:
        selected_index = select_potential_match_with_same_recordedattime(
            pm_index,
            route_history,
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
    route_history_1 = {  # noqa: RUF012 - BODS-7131
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
    route_history_2 = {  # noqa: RUF012 - BODS-7131
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
    route_history_3 = {  # noqa: RUF012 - BODS-7131
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
    route_history_4 = {  # noqa: RUF012 - BODS-7131
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
    route_history_5 = {  # noqa: RUF012 - BODS-7131
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
    route_history_6 = {  # noqa: RUF012 - BODS-7131
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
    route_history_7 = {  # noqa: RUF012 - BODS-7131
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
            "route_history",
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
                route_history_1,
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
                route_history_2,
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
                id="not first match, the pm index higher than the highest match index saved and it will be the third actual match, "
                "move the potential match to be a match and remove the lowest match index from matched stops",
            ),
            pytest.param(
                timetable,
                avl_record,
                "15",
                pm_details_3,
                route_history_3,
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
                id="not first match, the pm index lower than the lowest match index saved, "
                "remove current potential match from potential matches",
            ),
            pytest.param(
                timetable,
                avl_record,
                "23",
                pm_details_4,
                route_history_4,
                [],
                [],
                [],  # bad_matches
                ["23"],  # expected_potential_matches_to_delete
                [
                    {"timetable_id": 893823127},
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
                id="not first match, the pm index lower than the highest match index saved and it "
                "will be the third actual match, move the potential match to be a match and delete "
                "the indices that are higher than the current potential match index in the matched stops",
            ),
            pytest.param(
                timetable_2,
                avl_record_2,
                "7",
                pm_details_5,
                route_history_5,
                [],
                [],
                [],  # bad_matches
                ["7"],  # expected_potential_matches_to_delete
                [
                    {"timetable_id": 1091293465},
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
                id="bus going to the starting point to start the journey and matching backwards, "
                "when matching the second bus stop and there's only one actual match, "
                "delete the first matched stop",
            ),
            pytest.param(
                timetable_3,
                avl_record_3,
                "11",
                pm_details_6,
                route_history_6,
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
                route_history_7,
                [],
                [],
                [],  # bad_matches
                ["70"],  # expected_potential_matches_to_delete
                [
                    {"timetable_id": 1231325785},
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
        route_history: dict,
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
            route_history,
            potential_matches_to_delete,
            new_matches,
            bad_matches,
        )
        assert potential_matches_to_delete == expected_potential_matches_to_delete
        assert bad_matches == expected_bad_matches
        assert route_history["matched_stops"] == expected_matched_stops
        assert new_matches == expected_new_matches
