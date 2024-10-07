import datetime

from ingestion_pipelines.sirivm_otp_matching_function.sirivm_otp_matching_function.matcher.matching import (
    get_group_stop_history,
)


class TestGroupStopHistory:  # noqa: D101 - BODS-7131
    def test_group_stop_history_empty_stop_history(self) -> None:
        """Test getting group stop history with an empty stop history"""
        stop_history = {}
        group_id = "ABC12342024-09-01"
        group_stop_history = get_group_stop_history(group_id, stop_history)

        expected_group_stop_history = {
            "last_avl_time": "",
            "last_avl_index": 0,
            "matched_stops": {},
            "potential_matches": {},
        }

        assert group_stop_history == expected_group_stop_history

    def test_group_stop_history(self) -> None:
        """Test getting group stop history with a stop history with content"""
        stop_history = {
            "ABC12342024-09-01": {
                "last_avl_time": datetime.datetime(2024, 9, 1, 11, 34, 37),  # noqa: DTZ001 - BODS-7131
                "last_avl_index": 6,
                "matched_stops": {
                    "1": {"last_match_time": datetime.datetime(2024, 9, 1, 11, 32, 5)},  # noqa: DTZ001 - BODS-7131
                },
                "potential_matches": {
                    "2": {
                        "last_avl_index": 6,
                        "last_distance": 58.596598093401845,
                        "last_time_in_zone": datetime.datetime(2024, 9, 1, 11, 34, 37),  # noqa: DTZ001 - BODS-7131
                    },
                },
            },
        }
        group_id = "ABC12342024-09-01"
        group_stop_history = get_group_stop_history(group_id, stop_history)

        expected_group_stop_history = {
            "last_avl_time": datetime.datetime(2024, 9, 1, 11, 34, 37),  # noqa: DTZ001 - BODS-7131
            "last_avl_index": 6,
            "matched_stops": {
                "1": {"last_match_time": datetime.datetime(2024, 9, 1, 11, 32, 5)},  # noqa: DTZ001 - BODS-7131
            },
            "potential_matches": {
                "2": {
                    "last_avl_index": 6,
                    "last_distance": 58.596598093401845,
                    "last_time_in_zone": datetime.datetime(2024, 9, 1, 11, 34, 37),  # noqa: DTZ001 - BODS-7131
                },
            },
        }

        assert group_stop_history == expected_group_stop_history
