from datetime import datetime
import pytz

expected_set = {"TLCT37812152024-08-20": {}}
expected_remove = []
expected_stop_history = {
    "TLCT37812152024-08-20": {
        "last_avl_time": datetime(2024, 8, 20, 12, 0, 5).replace(tzinfo=pytz.utc),
        "last_avl_index": 91,
        "matched_stops": {
            "43": {
                "last_match_time": datetime(2024, 8, 20, 11, 59, 5).replace(
                    tzinfo=pytz.utc
                )
            },
            "44": {
                "last_match_time": datetime(
                    2024,
                    8,
                    20,
                    11,
                    59,
                    27,
                ).replace(tzinfo=pytz.utc)
            },
            "45": {
                "last_match_time": datetime(
                    2024,
                    8,
                    20,
                    11,
                    59,
                    57,
                ).replace(tzinfo=pytz.utc)
            },
        },
        "potential_matches": {
            "45": {
                "last_avl_index": 91,
                "last_distance": 9.786452000783465,
                "last_time_in_zone": datetime(2024, 8, 20, 12, 00, 5).replace(
                    tzinfo=pytz.utc
                )
            }
        },
    }
}
