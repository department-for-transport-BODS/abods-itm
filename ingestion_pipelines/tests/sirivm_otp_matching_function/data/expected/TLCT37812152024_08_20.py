from datetime import UTC, datetime  # noqa: N999 - BODS-7131

expected_set = {"TLCT|378|1215|2024-08-20": {}}
expected_remove = []
expected_stop_history = {
    "TLCT|378|1215|2024-08-20": {
        "last_avl_time": datetime(2024, 8, 20, 12, 0, 5, tzinfo=UTC),
        "last_avl_index": 91,
        "matched_stops": {
            "43": {
                "last_match_time": datetime(2024, 8, 20, 11, 59, 5, tzinfo=UTC),
            },
            "44": {
                "last_match_time": datetime(2024, 8, 20, 11, 59, 27, tzinfo=UTC),
            },
            "45": {
                "last_match_time": datetime(2024, 8, 20, 11, 59, 57, tzinfo=UTC),
            },
        },
        "potential_matches": {
            "45": {
                "last_avl_index": 91,
                "last_distance": 9.786452000783465,
                "last_time_in_zone": datetime(2024, 8, 20, 12, 00, 5, tzinfo=UTC),
            },
        },
    },
}
