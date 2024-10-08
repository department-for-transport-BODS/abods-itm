from typing import Any

import pytest
import os
from unittest import mock
from .data.get_test_data import read_avl, read_timetable, get_shards
import datetime
import pytz
from ingestion_pipelines.sirivm_otp_matching_function.sirivm_otp_matching_function.matcher.matching import (
    check_update_first_stop,
    find_matches_in_potential_matches,
    remove_matched_stops,
    update_matched_stop,
    write_matched_stop_to_db,
    get_timetable_departure_time,
    update_potential_match,
    select_potential_match_with_same_recordedattime,
    move_potential_match_to_match,
    positions_timetable_lookup,
)
from ingestion_pipelines.sirivm_otp_matching_function.sirivm_otp_matching_function.matcher.utils import (
    OtpState,
)
from ingestion_pipelines.sirivm_otp_matching_function.sirivm_otp_matching_function.matcher.models import (
    AVLRecord,
)
from .data.expected.TLCT37812152024_08_20 import (
    expected_stop_history,
    expected_set,
    expected_remove,
)


class TestCheckUpdateFirstStop:
    avl_record = AVLRecord(read_avl("check_update_first_stop.csv")[1][0])
    avl_record_5_mins = AVLRecord(read_avl("check_update_first_stop.csv")[0][0])
    timetable = read_timetable("TLCT37812152024-08-20.json")
    group_id = "TLCT37812152024-08-20"
    stop_pos_distances_remove_5_mins = []
    group_stop_history_5_mins = {
        "last_avl_time": datetime.datetime(2024, 8, 20, 11, 24, 58).replace(
            tzinfo=pytz.utc
        ),
        "last_avl_index": 6,
        "matched_stops": {
            "1": {
                "last_match_time": datetime.datetime(2024, 8, 20, 11, 23, 48).replace(
                    tzinfo=pytz.utc
                )
            }
        },
        "potential_matches": {
            "2": {
                "last_avl_index": 6,
                "last_distance": 58.596598093401845,
                "last_time_in_zone": datetime.datetime(2024, 8, 20, 11, 24, 58).replace(
                    tzinfo=pytz.utc
                ),
            }
        },
    }
    expected_matched_stops_5_mins = {}
    expected_potential_matches_5_mins = {
        "1": {
            "last_avl_index": 8,
            "last_distance": 37.35876375439114,
            "last_time_in_zone": avl_record_5_mins.recorded_at_time_utc,
        },
        "2": {
            "last_avl_index": 6,
            "last_distance": 58.596598093401845,
            "last_time_in_zone": datetime.datetime(2024, 8, 20, 11, 24, 58).replace(
                tzinfo=pytz.utc
            ),
        },
    }
    expected_stop_pos_distances_remove_5_mins = [
        ("1", 893823336, "TLCT37812152024-08-20")
    ]
    group_stop_history = {
        "last_avl_time": datetime.datetime(2024, 8, 20, 11, 34, 37).replace(
            tzinfo=pytz.utc
        ),
        "last_avl_index": 6,
        "matched_stops": {
            "1": {
                "last_match_time": datetime.datetime(2024, 8, 20, 11, 32, 5).replace(
                    tzinfo=pytz.utc
                )
            }
        },
        "potential_matches": {
            "2": {
                "last_avl_index": 6,
                "last_distance": 58.596598093401845,
                "last_time_in_zone": datetime.datetime(2024, 8, 20, 11, 34, 37).replace(
                    tzinfo=pytz.utc
                ),
            }
        },
    }
    stop_pos_distances_remove = []
    expected_matched_stops = {
        "1": {
            "last_match_time": datetime.datetime(2024, 8, 20, 11, 32, 5).replace(
                tzinfo=pytz.utc
            )
        }
    }
    expected_potential_matches = {
        "2": {
            "last_avl_index": 6,
            "last_distance": 58.596598093401845,
            "last_time_in_zone": datetime.datetime(2024, 8, 20, 11, 34, 37).replace(
                tzinfo=pytz.utc
            ),
        }
    }
    expected_stop_pos_distances_remove = []
    current_avl_index = 8

    def mockenv(**envvars):
        return mock.patch.dict(os.environ, envvars)

    @mockenv(OPERATOR_REF="TLCT", LINE_NAME="378")
    @pytest.mark.parametrize(
        "rec, timetable_dict, group_stop_history, stop_pos_distances_remove, current_avl_index, expected_matched_stops, expected_potential_matches, expected_stop_pos_distances_remove",
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
    def test_check_update_first_stop_avl_within_5_mins(
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
            timetable_dict,
            group_stop_history,
            stop_pos_distances_remove,
            current_avl_index,
        )
        assert group_stop_history["matched_stops"] == expected_matched_stops
        assert group_stop_history["potential_matches"] == expected_potential_matches
        assert stop_pos_distances_remove == expected_stop_pos_distances_remove


class TestFindMatchesInPotentialMatches:
    avl_record = AVLRecord(read_avl("TLCT37812152024-08-20.csv")[73][0])
    avl_record_2 = AVLRecord(read_avl("TLCT37812152024-08-20.csv")[220][0])
    avl_record_3 = AVLRecord(read_avl("TLCT37812152024-08-20.csv")[222][0])
    avl_record_4 = AVLRecord(read_avl("TLCT37812152024-08-20.csv")[183][0])
    timetable = read_timetable("TLCT37812152024-08-20.json")
    group_id = "TLCT37812152024-08-20"
    group_stop_history = {
        "last_avl_index": 30,
        "last_avl_time": datetime.datetime(2024, 8, 20, 11, 35, 25).replace(
            tzinfo=pytz.utc
        ),
        "matched_stops": {
            "3": {
                "last_match_time": datetime.datetime(2024, 8, 20, 11, 31, 53).replace(
                    tzinfo=pytz.utc
                ),
            },
            "4": {
                "last_match_time": datetime.datetime(2024, 8, 20, 11, 32, 20).replace(
                    tzinfo=pytz.utc
                ),
            },
            "5": {
                "last_match_time": datetime.datetime(2024, 8, 20, 11, 32, 50).replace(
                    tzinfo=pytz.utc
                ),
            },
        },
        "potential_matches": {
            "6": {
                "last_avl_index": 29,
                "last_distance": 142,
                "last_time_in_zone": datetime.datetime(2024, 8, 20, 11, 34, 42).replace(
                    tzinfo=pytz.utc
                ),
            }
        },
    }
    group_stop_history_2 = {
        "last_avl_index": 90,
        "last_avl_time": datetime.datetime(2024, 8, 20, 11, 59, 57).replace(
            tzinfo=pytz.utc
        ),
        "matched_stops": {
            "41": {
                "last_match_time": datetime.datetime(2024, 8, 20, 11, 58, 3).replace(
                    tzinfo=pytz.utc
                ),
            },
            "42": {
                "last_match_time": datetime.datetime(2024, 8, 20, 11, 58, 43).replace(
                    tzinfo=pytz.utc
                ),
            },
            "43": {
                "last_match_time": datetime.datetime(2024, 8, 20, 11, 59, 5).replace(
                    tzinfo=pytz.utc
                ),
            },
        },
        "potential_matches": {
            "45": {
                "last_avl_index": 89,
                "last_distance": 11,
                "last_time_in_zone": datetime.datetime(2024, 8, 20, 11, 59, 57).replace(
                    tzinfo=pytz.utc
                ),
            },
            "44": {
                "last_avl_index": 89,
                "last_distance": 13,
                "last_time_in_zone": datetime.datetime(2024, 8, 20, 11, 59, 27).replace(
                    tzinfo=pytz.utc
                ),
            },
        },
    }
    group_stop_history_3 = {
        "last_avl_index": 91,
        "last_avl_time": datetime.datetime(2024, 8, 20, 12, 00, 5).replace(
            tzinfo=pytz.utc
        ),
        "matched_stops": {
            "42": {
                "last_match_time": datetime.datetime(2024, 8, 20, 11, 58, 43).replace(
                    tzinfo=pytz.utc
                ),
            },
            "43": {
                "last_match_time": datetime.datetime(2024, 8, 20, 11, 59, 5).replace(
                    tzinfo=pytz.utc
                ),
            },
            "45": {
                "last_match_time": datetime.datetime(2024, 8, 20, 11, 59, 57).replace(
                    tzinfo=pytz.utc
                ),
            },
        },
        "potential_matches": {
            "44": {
                "last_avl_index": 90,
                "last_distance": 332,
                "last_time_in_zone": datetime.datetime(2024, 8, 20, 11, 59, 27).replace(
                    tzinfo=pytz.utc
                ),
            },
        },
    }
    group_stop_history_4 = {
        "last_avl_index": 77,
        "last_avl_time": datetime.datetime(2024, 8, 20, 11, 54, 9).replace(
            tzinfo=pytz.utc
        ),
        "matched_stops": {
            "33": {
                "last_match_time": datetime.datetime(2024, 8, 20, 11, 50, 28).replace(
                    tzinfo=pytz.utc
                ),
            },
            "34": {
                "last_match_time": datetime.datetime(2024, 8, 20, 11, 51, 35).replace(
                    tzinfo=pytz.utc
                ),
            },
            "35": {
                "last_match_time": datetime.datetime(2024, 8, 20, 11, 53, 8).replace(
                    tzinfo=pytz.utc
                ),
            },
        },
        "potential_matches": {
            "36": {
                "last_avl_index": 76,
                "last_distance": 8,
                "last_time_in_zone": datetime.datetime(2024, 8, 20, 11, 53, 43).replace(
                    tzinfo=pytz.utc
                ),
            },
        },
    }
    batch_id = "123"

    def mockenv(**envvars):
        return mock.patch.dict(os.environ, envvars)

    @mockenv(OPERATOR_REF="TLCT", LINE_NAME="378")
    @pytest.mark.parametrize(
        "avl, timetable_dict, group_stop_history, current_avl_index, batch_id, stop_pos_distances, potential_matches_to_delete, final_stop_index, stop_pos_distances_remove, expected_group_stop_history, expected_potential_matches_to_delete",
        [
            pytest.param(
                avl_record,
                timetable,
                group_stop_history,
                30,
                batch_id,
                {group_id: {}},  # stop pos dist
                [],  # potential_matches_to_delete
                45,  # final_stop_index
                [],  # stop_pos_distances_remove,
                {
                    "last_avl_index": 30,
                    "last_avl_time": datetime.datetime(2024, 8, 20, 11, 35, 25).replace(
                        tzinfo=pytz.utc
                    ),
                    "matched_stops": {
                        "4": {
                            "last_match_time": datetime.datetime(
                                2024, 8, 20, 11, 32, 20
                            ).replace(tzinfo=pytz.utc),
                        },
                        "5": {
                            "last_match_time": datetime.datetime(
                                2024, 8, 20, 11, 32, 50
                            ).replace(tzinfo=pytz.utc),
                        },
                        "6": {
                            "last_match_time": datetime.datetime(
                                2024, 8, 20, 11, 34, 42
                            ).replace(tzinfo=pytz.utc),
                        },
                    },
                    "potential_matches": {
                        "6": {
                            "last_avl_index": 29,
                            "last_distance": 142,
                            "last_time_in_zone": datetime.datetime(
                                2024, 8, 20, 11, 34, 42
                            ).replace(tzinfo=pytz.utc),
                        }
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
                batch_id,
                {group_id: {}},  # stop pos dist
                [],  # potential_matches_to_delete
                45,  # final_stop_index
                [],  # stop_pos_distances_remove,
                {
                    "last_avl_index": 90,
                    "last_avl_time": datetime.datetime(2024, 8, 20, 11, 59, 57).replace(
                        tzinfo=pytz.utc
                    ),
                    "matched_stops": {
                        "42": {
                            "last_match_time": datetime.datetime(
                                2024, 8, 20, 11, 58, 43
                            ).replace(tzinfo=pytz.utc),
                        },
                        "43": {
                            "last_match_time": datetime.datetime(
                                2024, 8, 20, 11, 59, 5
                            ).replace(tzinfo=pytz.utc),
                        },
                        "45": {
                            "last_match_time": datetime.datetime(
                                2024, 8, 20, 11, 59, 57
                            ).replace(tzinfo=pytz.utc),
                        },
                    },
                    "potential_matches": {
                        "45": {
                            "last_avl_index": 89,
                            "last_distance": 11,
                            "last_time_in_zone": datetime.datetime(
                                2024, 8, 20, 11, 59, 57
                            ).replace(tzinfo=pytz.utc),
                        },
                        "44": {
                            "last_avl_index": 90,
                            "last_distance": 332.5369444168041,
                            "last_time_in_zone": datetime.datetime(
                                2024, 8, 20, 11, 59, 27
                            ).replace(tzinfo=pytz.utc),
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
                batch_id,
                {group_id: {}},  # stop pos dist
                [],  # potential_matches_to_delete
                45,  # final_stop_index
                [],  # stop_pos_distances_remove,
                {
                    "last_avl_index": 91,
                    "last_avl_time": datetime.datetime(2024, 8, 20, 12, 00, 5).replace(
                        tzinfo=pytz.utc
                    ),
                    "matched_stops": {
                        "43": {
                            "last_match_time": datetime.datetime(
                                2024, 8, 20, 11, 59, 5
                            ).replace(tzinfo=pytz.utc),
                        },
                        "44": {
                            "last_match_time": datetime.datetime(
                                2024, 8, 20, 11, 59, 27
                            ).replace(tzinfo=pytz.utc)
                        },
                        "45": {
                            "last_match_time": datetime.datetime(
                                2024, 8, 20, 11, 59, 57
                            ).replace(tzinfo=pytz.utc),
                        },
                    },
                    "potential_matches": {
                        "44": {
                            "last_avl_index": 90,
                            "last_distance": 332,
                            "last_time_in_zone": datetime.datetime(
                                2024, 8, 20, 11, 59, 27
                            ).replace(tzinfo=pytz.utc),
                        }
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
                batch_id,
                {group_id: {}},  # stop pos dist
                [],  # potential_matches_to_delete
                45,  # final_stop_index
                [],  # stop_pos_distances_remove,
                {
                    "last_avl_index": 77,
                    "last_avl_time": datetime.datetime(2024, 8, 20, 11, 54, 9).replace(
                        tzinfo=pytz.utc
                    ),
                    "matched_stops": {
                        "33": {
                            "last_match_time": datetime.datetime(
                                2024, 8, 20, 11, 50, 28
                            ).replace(tzinfo=pytz.utc),
                        },
                        "34": {
                            "last_match_time": datetime.datetime(
                                2024, 8, 20, 11, 51, 35
                            ).replace(tzinfo=pytz.utc),
                        },
                        "35": {
                            "last_match_time": datetime.datetime(
                                2024, 8, 20, 11, 53, 8
                            ).replace(tzinfo=pytz.utc),
                        },
                    },
                    "potential_matches": {
                        "36": {
                            "last_avl_index": 77,
                            "last_distance": 15.608686190208905,
                            "last_time_in_zone": datetime.datetime(
                                2024, 8, 20, 11, 54, 9
                            ).replace(tzinfo=pytz.utc),
                        },
                    },
                },
                [],
                id="the potential match is not a final stop and avl_pm_distance is less than threshold, update potential match details",
            ),
        ],
    )
    def test_find_matches_in_potential_matches(
        self,
        avl: AVLRecord,
        timetable_dict: dict,
        group_stop_history: dict,
        current_avl_index: int,
        batch_id: str,
        stop_pos_distances: dict,
        potential_matches_to_delete: list,
        final_stop_index: int,
        stop_pos_distances_remove: list,
        expected_group_stop_history: dict,
        expected_potential_matches_to_delete: list,
    ):
        find_matches_in_potential_matches(
            avl,
            timetable_dict,
            group_stop_history,
            current_avl_index,
            batch_id,
            stop_pos_distances,
            potential_matches_to_delete,
            final_stop_index,
            stop_pos_distances_remove,
        )
        assert group_stop_history == expected_group_stop_history
        assert potential_matches_to_delete == expected_potential_matches_to_delete


class TestRemoveMatchedStops:
    timetable = read_timetable("TLCT37812152024-08-20.json")
    delete_from = "potential_matches"
    matches_to_delete = ["2"]

    def test_remove_matched_stops(self):
        group_stop_history = {
            "last_avl_time": datetime.datetime(2024, 9, 1, 11, 34, 37),
            "last_avl_index": 6,
            "matched_stops": {
                "1": {"last_match_time": datetime.datetime(2024, 9, 1, 11, 32, 5)}
            },
            "potential_matches": {
                "2": {
                    "last_avl_index": 6,
                    "last_distance": 58.596598093401845,
                    "last_time_in_zone": datetime.datetime(2024, 9, 1, 11, 34, 37),
                }
            },
        }
        expected_group_stop_history = {
            "last_avl_time": datetime.datetime(2024, 9, 1, 11, 34, 37),
            "last_avl_index": 6,
            "matched_stops": {
                "1": {"last_match_time": datetime.datetime(2024, 9, 1, 11, 32, 5)}
            },
            "potential_matches": {},
        }
        remove_matched_stops(
            group_stop_history, self.delete_from, self.matches_to_delete
        )
        assert group_stop_history == expected_group_stop_history


class TestUpdateMatchedStop:
    avl_record = AVLRecord(read_avl("TLCT37812152024-08-20.csv")[0][0])
    pm_index = "1"
    last_time_in_zone = datetime.datetime(2024, 9, 1, 11, 32, 5)
    group_stop_history = {
        "last_avl_time": datetime.datetime(2024, 9, 1, 11, 30, 57),
        "last_avl_index": 3,
        "matched_stops": {},
        "potential_matches": {
            "1": {
                "last_avl_index": 3,
                "last_distance": 58.596598093401845,
                "last_time_in_zone": datetime.datetime(2024, 9, 1, 11, 30, 57),
            }
        },
    }
    potential_matches_to_delete = []

    def mockenv(**envvars):
        return mock.patch.dict(os.environ, envvars)

    @mockenv(OPERATOR_REF="TLCT", LINE_NAME="378")
    def test_update_matched_stop(self):
        update_matched_stop(
            self.avl_record,
            self.pm_index,
            self.last_time_in_zone,
            self.group_stop_history,
            self.potential_matches_to_delete,
        )
        expected_group_stop_history = {
            "last_avl_time": datetime.datetime(2024, 9, 1, 11, 30, 57),
            "last_avl_index": 3,
            "matched_stops": {
                "1": {"last_match_time": datetime.datetime(2024, 9, 1, 11, 32, 5)}
            },
            "potential_matches": {
                "1": {
                    "last_avl_index": 3,
                    "last_distance": 58.596598093401845,
                    "last_time_in_zone": datetime.datetime(2024, 9, 1, 11, 30, 57),
                }
            },
        }
        expected_potential_matches_to_delete = ["1"]
        assert self.group_stop_history == expected_group_stop_history
        assert self.potential_matches_to_delete == expected_potential_matches_to_delete


class TestWriteMatchedStopToDb:
    timetable = read_timetable("TLCT37812152024-08-20.json")
    stop_pos_distances_non_final = {"TLCT37812152024-08-20": {}}
    stop_pos_distances_final = {"TLCT37812152024-08-20": {}}
    group_id = "TLCT37812152024-08-20"
    batch_id = "123"
    last_time_in_zone_non_final = datetime.datetime(2024, 8, 20, 11, 9, 5).replace(
        tzinfo=pytz.utc
    )
    last_time_in_zone_final = datetime.datetime(2024, 8, 20, 11, 35, 0).replace(
        tzinfo=pytz.utc
    )

    expected_stop_pos_distances_non_final = {
        "1": (
            -355.0,
            "11:09:05",
            893823336,
            group_id,
            batch_id,
            last_time_in_zone_non_final,
            OtpState.EARLY,
            "Non-final",
        ),
    }
    expected_stop_pos_distances_final = {
        "45": (
            -420.0,
            "11:35:00",
            893822665,
            group_id,
            batch_id,
            last_time_in_zone_final,
            OtpState.ON_TIME,
            "final",
        ),
    }

    @pytest.mark.parametrize(
        "is_final_stop, timetable_dict, stop_pos_distances, group_id, pm_index, last_time_in_zone, batch_id, expected_stop_pos_distances",
        [
            pytest.param(
                False,
                timetable,
                stop_pos_distances_non_final,
                group_id,
                "1",
                last_time_in_zone_non_final,
                batch_id,
                expected_stop_pos_distances_non_final,
                id="Write non-final stop to db",
            ),
            pytest.param(
                True,
                timetable,
                stop_pos_distances_final,
                group_id,
                "45",
                last_time_in_zone_final,
                batch_id,
                expected_stop_pos_distances_final,
                id="Write final stop to db",
            ),
        ],
    )
    def test_write_matched_final_stop_to_db(
        self,
        is_final_stop: bool,
        timetable_dict: dict,
        stop_pos_distances: dict,
        group_id: str,
        pm_index: str,
        last_time_in_zone: datetime,
        batch_id: str,
        expected_stop_pos_distances: Any,
    ):
        write_matched_stop_to_db(
            is_final_stop,
            timetable_dict,
            stop_pos_distances,
            group_id,
            pm_index,
            last_time_in_zone,
            batch_id,
        )
        assert stop_pos_distances[group_id] == expected_stop_pos_distances


class TestGetTimetableDepartureTime:
    timetable = read_timetable("TLCT37812152024-08-20.json")
    group_id = "TLCT37812152024-08-20"
    pm_index = "2"

    def test_get_timetable_departure_time(self):
        timetable_departure_time = get_timetable_departure_time(
            self.timetable, self.group_id, self.pm_index
        )
        expected_timtable_departure_time = datetime.datetime(
            2024, 8, 20, 11, 16, 0
        ).replace(tzinfo=pytz.utc)
        assert timetable_departure_time == expected_timtable_departure_time


class TestUpdatePotentialMatch:
    avl_record = AVLRecord(read_avl("update_potential_match.csv")[0][0])
    avl_record_wo_datetime = AVLRecord(read_avl("update_potential_match.csv")[1][0])
    pm_index = "1"
    current_avl_index = 4
    expected_pm_details_w_datetime = {
        "last_avl_index": 4,
        "last_distance": 12.123214,
        "last_time_in_zone": datetime.datetime(2024, 8, 20, 11, 26, 42).replace(
            tzinfo=pytz.utc
        ),
    }
    expected_pm_details_wo_datetime = {
        "last_avl_index": 4,
        "last_distance": 72.12345678,
        "last_time_in_zone": datetime.datetime(2024, 8, 20, 11, 25, 57).replace(
            tzinfo=pytz.utc
        ),
    }

    def mockenv(**envvars):
        return mock.patch.dict(os.environ, envvars)

    @mockenv(OPERATOR_REF="TLCT", LINE_NAME="378")
    @pytest.mark.parametrize(
        "avl, pm_index, pm_details, current_avl_index, avl_pm_distance, update_recorded_at_time, expected_pm_details",
        [
            pytest.param(
                avl_record,
                pm_index,
                {
                    "last_avl_index": 3,
                    "last_distance": 58.596598093401845,
                    "last_time_in_zone": datetime.datetime(
                        2024, 8, 20, 11, 25, 57
                    ).replace(tzinfo=pytz.utc),
                },
                current_avl_index,
                12.123214,
                True,
                expected_pm_details_w_datetime,
                id="With datetime provided, update the last_avl_index, last_distance and last_time_in_zone",
            ),
            pytest.param(
                avl_record,
                pm_index,
                {
                    "last_avl_index": 3,
                    "last_distance": 58.596598093401845,
                    "last_time_in_zone": datetime.datetime(
                        2024, 8, 20, 11, 25, 57
                    ).replace(tzinfo=pytz.utc),
                },
                current_avl_index,
                72.12345678,
                False,
                expected_pm_details_wo_datetime,
                id="With datetime provided, only update the last_avl_index and last_distance",
            ),
        ],
    )
    def test_update_potential_match(
        self,
        avl: AVLRecord,
        pm_index: str,
        pm_details: dict,
        current_avl_index: int,
        avl_pm_distance: float,
        update_recorded_at_time: bool,
        expected_pm_details: dict,
    ):
        update_potential_match(
            avl,
            pm_index,
            pm_details,
            current_avl_index,
            avl_pm_distance,
            update_recorded_at_time,
        )
        assert pm_details == expected_pm_details


class TestSelectPotentialMatchWithSameRecordedattime:
    group_stop_history_same_recordedattime = {
        "last_avl_index": 40,
        "last_avl_time": datetime.datetime(2024, 8, 23, 11, 16, 14),
        "matched_stops": {
            "39": {"last_match_time": datetime.datetime(2024, 8, 23, 11, 14, 41)},
            "3": {"last_match_time": datetime.datetime(2024, 8, 23, 11, 15, 5)},
        },
        "potential_matches": {
            "4": {
                "last_avl_index": 39,
                "last_distance": 311.19398802530185,
                "last_time_in_zone": datetime.datetime(2024, 8, 23, 11, 15, 36),
            },
            "38": {
                "last_avl_index": 39,
                "last_distance": 294.4630341883636,
                "last_time_in_zone": datetime.datetime(2024, 8, 23, 11, 15, 36),
            },
            "5": {
                "last_avl_index": 40,
                "last_distance": 17.612857082239692,
                "last_time_in_zone": datetime.datetime(2024, 8, 23, 11, 16, 14),
            },
            "37": {
                "last_avl_index": 39,
                "last_distance": 18.62101754791971,
                "last_time_in_zone": datetime.datetime(2024, 8, 23, 11, 16),
            },
        },
    }
    group_stop_history_wo_same_recordedattime = {
        "last_avl_index": 3,
        "last_avl_time": datetime.datetime(2024, 8, 23, 10, 57, 48),
        "potential_matches": {
            "1": {
                "last_avl_index": 3,
                "last_distance": 40.03840622665115,
                "last_time_in_zone": datetime.datetime(2024, 8, 23, 10, 57, 48),
            }
        },
        "matched_stops": {},
    }
    avl_record = AVLRecord(read_avl("TLCT37812152024-08-20.csv")[0][0])

    def mockenv(**envvars):
        return mock.patch.dict(os.environ, envvars)

    @mockenv(OPERATOR_REF="TLCT", LINE_NAME="378")
    @pytest.mark.parametrize(
        "avl_record, pm_index, group_stop_history, potential_matches_to_delete, expected_selected_index, expected_potential_matches_to_delete",
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
                "1",
                group_stop_history_wo_same_recordedattime,
                [],
                "1",
                [],
                id="No potential matches are with the same recorded_at_time, return the current potential index",
            ),
        ],
    )
    def test_select_potential_match_with_same_recordedattime(
        self,
        avl_record: AVLRecord,
        pm_index: str,
        group_stop_history: dict,
        potential_matches_to_delete: list,
        expected_selected_index: str,
        expected_potential_matches_to_delete: list,
    ):
        selected_index = select_potential_match_with_same_recordedattime(
            avl_record, pm_index, group_stop_history, potential_matches_to_delete
        )
        assert selected_index == expected_selected_index
        assert potential_matches_to_delete == expected_potential_matches_to_delete


class TestMovePotentialMatchToMatch:
    avl_record = AVLRecord(read_avl("TLCT37812152024-08-20.csv")[0][0])
    timetable = read_timetable("TLCT37812152024-08-20.json")
    group_id = "TLCT37812152024-08-20"
    final_stop_index = "41"
    pm_details_1 = {
        "last_avl_index": 3,
        "last_distance": 75.1243252308765,
        "last_time_in_zone": datetime.datetime(2024, 8, 20, 11, 15, 48).replace(
            tzinfo=pytz.utc
        ),
    }
    group_stop_history_1 = {
        "last_avl_index": 3,
        "last_avl_time": datetime.datetime(2024, 8, 20, 11, 15, 48).replace(
            tzinfo=pytz.utc
        ),
        "potential_matches": {
            "1": {
                "last_avl_index": 3,
                "last_distance": 75.1243252308765,
                "last_time_in_zone": datetime.datetime(2024, 8, 20, 11, 15, 48).replace(
                    tzinfo=pytz.utc
                ),
            }
        },
        "matched_stops": {},
    }
    pm_details_2 = {
        "last_avl_index": 30,
        "last_distance": 80.65435437,
        "last_time_in_zone": datetime.datetime(2024, 8, 20, 11, 20, 4).replace(
            tzinfo=pytz.utc
        ),
    }
    group_stop_history_2 = {
        "last_avl_index": 30,
        "last_avl_time": datetime.datetime(2024, 8, 20, 11, 20, 4).replace(
            tzinfo=pytz.utc
        ),
        "potential_matches": {
            "3": {
                "last_avl_index": 30,
                "last_distance": 80.65435437,
                "last_time_in_zone": datetime.datetime(2024, 8, 20, 11, 20, 4).replace(
                    tzinfo=pytz.utc
                ),
            }
        },
        "matched_stops": {
            "1": {
                "last_match_time": datetime.datetime(2024, 8, 20, 11, 15, 48).replace(
                    tzinfo=pytz.utc
                )
            },
            "2": {
                "last_match_time": datetime.datetime(2024, 8, 20, 11, 17, 6).replace(
                    tzinfo=pytz.utc
                )
            },
        },
    }
    pm_details_3 = {
        "last_avl_index": 59,
        "last_distance": 72.1232432,
        "last_time_in_zone": datetime.datetime(2024, 8, 20, 11, 39, 54).replace(
            tzinfo=pytz.utc
        ),
    }
    group_stop_history_3 = {
        "last_avl_index": 59,
        "last_avl_time": datetime.datetime(2024, 8, 20, 11, 39, 54).replace(
            tzinfo=pytz.utc
        ),
        "potential_matches": {
            "15": {
                "last_avl_index": 59,
                "last_distance": 72.1232432,
                "last_time_in_zone": datetime.datetime(2024, 8, 20, 11, 37, 54).replace(
                    tzinfo=pytz.utc
                ),
            },
            "23": {
                "last_avl_index": 59,
                "last_distance": 15.12312678,
                "last_time_in_zone": datetime.datetime(2024, 8, 20, 11, 39, 54).replace(
                    tzinfo=pytz.utc
                ),
            },
        },
        "matched_stops": {
            "20": {
                "last_match_time": datetime.datetime(2024, 8, 20, 11, 32, 23).replace(
                    tzinfo=pytz.utc
                )
            },
            "21": {
                "last_match_time": datetime.datetime(2024, 8, 20, 11, 34, 23).replace(
                    tzinfo=pytz.utc
                )
            },
            "22": {
                "last_match_time": datetime.datetime(2024, 8, 20, 11, 35, 6).replace(
                    tzinfo=pytz.utc
                )
            },
        },
    }

    pm_details_4 = {
        "last_avl_index": 59,
        "last_distance": 81.123124167,
        "last_time_in_zone": datetime.datetime(2024, 8, 20, 11, 36, 54).replace(
            tzinfo=pytz.utc
        ),
    }
    group_stop_history_4 = {
        "last_avl_index": 62,
        "last_avl_time": datetime.datetime(2024, 8, 20, 11, 39, 54).replace(
            tzinfo=pytz.utc
        ),
        "potential_matches": {
            "23": {
                "last_avl_index": 59,
                "last_distance": 81.123124167,
                "last_time_in_zone": datetime.datetime(2024, 8, 20, 11, 36, 54).replace(
                    tzinfo=pytz.utc
                ),
            },
        },
        "matched_stops": {
            "21": {
                "last_match_time": datetime.datetime(2024, 8, 20, 11, 34, 23).replace(
                    tzinfo=pytz.utc
                )
            },
            "24": {
                "last_match_time": datetime.datetime(2024, 8, 20, 11, 35, 6).replace(
                    tzinfo=pytz.utc
                )
            },
        },
    }

    def mockenv(**envvars):
        return mock.patch.dict(os.environ, envvars)

    @mockenv(OPERATOR_REF="TLCT", LINE_NAME="378")
    @pytest.mark.parametrize(
        "final_stop_index, timetable_dict, avl, pm_index, pm_details, group_stop_history, potential_matches_to_delete, stop_pos_distances, batch_id, stop_pos_distances_remove, expected_potential_matches_to_delete, expected_stop_pos_distances_remove, expected_matched_stops, expected_stop_pos_distances",
        [
            pytest.param(
                final_stop_index,
                timetable,
                avl_record,
                "1",
                pm_details_1,
                group_stop_history_1,
                [],
                {group_id: {}},
                "123",
                [],  # stop pos distances remove
                ["1"],  # expected pm to delete
                [],  # expected stop pos dist remove
                {
                    "1": {
                        "last_match_time": datetime.datetime(
                            2024, 8, 20, 11, 15, 48
                        ).replace(tzinfo=pytz.utc)
                    }
                },
                {
                    group_id: {
                        "1": (
                            48.0,
                            "11:15:48",
                            893823336,
                            group_id,
                            "123",
                            datetime.datetime(2024, 8, 20, 11, 15, 48).replace(
                                tzinfo=pytz.utc
                            ),
                            OtpState.ON_TIME,
                            "Non-final",
                        )
                    }
                },
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
                {group_id: {}},
                "123",
                [],  # stop_pos_distances_remove
                ["3"],  # expected_potential_matches_to_delete
                [],  # expected_stop_pos_distances_remove
                {
                    "1": {
                        "last_match_time": datetime.datetime(
                            2024, 8, 20, 11, 15, 48
                        ).replace(tzinfo=pytz.utc)
                    },
                    "2": {
                        "last_match_time": datetime.datetime(
                            2024, 8, 20, 11, 17, 6
                        ).replace(tzinfo=pytz.utc)
                    },
                    "3": {
                        "last_match_time": datetime.datetime(
                            2024, 8, 20, 11, 20, 4
                        ).replace(tzinfo=pytz.utc)
                    },
                },
                {
                    group_id: {
                        "3": (
                            184.0,
                            "11:20:04",
                            893823358,
                            group_id,
                            "123",
                            datetime.datetime(2024, 8, 20, 11, 20, 4).replace(
                                tzinfo=pytz.utc
                            ),
                            OtpState.ON_TIME,
                            "Non-final",
                        )
                    }
                },
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
                {group_id: {}},
                "123",
                [],
                ["15"],
                [],
                {
                    "20": {
                        "last_match_time": datetime.datetime(2024, 8, 20, 11, 32, 23).replace(
                            tzinfo=pytz.utc
                        )
                    },
                    "21": {
                        "last_match_time": datetime.datetime(
                            2024, 8, 20, 11, 34, 23
                        ).replace(tzinfo=pytz.utc)
                    },
                    "22": {
                        "last_match_time": datetime.datetime(
                            2024, 8, 20, 11, 35, 6
                        ).replace(tzinfo=pytz.utc)
                    },
                },
                {group_id: {}},
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
                {group_id: {}},
                "123",
                [],  # stop_pos_distances_remove
                ["23"],  # expected_potential_matches_to_delete
                [("24", 893823127, group_id)],  # expected_stop_pos_distances_remove
                {
                    "21": {
                        "last_match_time": datetime.datetime(
                            2024, 8, 20, 11, 34, 23
                        ).replace(tzinfo=pytz.utc)
                    },
                    "23": {
                        "last_match_time": datetime.datetime(
                            2024, 8, 20, 11, 36, 54
                        ).replace(tzinfo=pytz.utc)
                    },
                },
                {
                    group_id: {
                        "23": (
                            534.0,
                            "11:36:54",
                            893823138,
                            group_id,
                            "123",
                            datetime.datetime(2024, 8, 20, 11, 36, 54).replace(
                                tzinfo=pytz.utc
                            ),
                            OtpState.LATE,
                            "Non-final",
                        )
                    }
                },
                id="not first match, the pm index lower than the highest match index saved and it will be the third actual match, move the potential match to be a match and delete the indices that are higher than the current potential match index in the matched stops",
            ),
        ],
    )
    def test_move_potential_match_to_match(
        self,
        final_stop_index: int,
        timetable_dict: dict,
        avl: AVLRecord,
        pm_index: str,
        pm_details: dict,
        group_stop_history: dict,
        potential_matches_to_delete: list,
        stop_pos_distances: dict,
        batch_id: str,
        stop_pos_distances_remove: list,
        expected_potential_matches_to_delete: list,
        expected_stop_pos_distances_remove: list,
        expected_matched_stops: dict,
        expected_stop_pos_distances: dict,
    ):
        move_potential_match_to_match(
            final_stop_index,
            timetable_dict,
            avl,
            pm_index,
            pm_details,
            group_stop_history,
            potential_matches_to_delete,
            stop_pos_distances,
            batch_id,
            stop_pos_distances_remove,
        )
        assert potential_matches_to_delete == expected_potential_matches_to_delete
        assert stop_pos_distances_remove == expected_stop_pos_distances_remove
        assert group_stop_history["matched_stops"] == expected_matched_stops
        assert stop_pos_distances == expected_stop_pos_distances


class TestPositionsTimetableLookup:
    shards = get_shards("shards.json")
    shard_no = "0"
    avl_list = read_avl("TLCT37812152024-08-20.csv")
    avl_dict = []
    for avl in avl_list:
        avl_dict.append(AVLRecord(avl[0]))
    timetable = read_timetable("TLCT37812152024-08-20.json")
    batch_id = "123"
    stop_history = {}

    def mockenv(**envvars):
        return mock.patch.dict(os.environ, envvars)

    @mockenv(OPERATOR_REF="TLCT", LINE_NAME="378")
    def test_positions_timetable_lookup(self):
        to_set, to_remove, stop_history = positions_timetable_lookup(
            self.timetable,
            self.shards,
            self.shard_no,
            self.avl_dict,
            self.batch_id,
            self.stop_history,
        )
        assert to_set == expected_set
        assert to_remove == expected_remove
        assert self.stop_history == expected_stop_history
