from datetime import UTC, datetime

from ingestion_pipelines.sirivm_otp_matching_function.app import ProcessingResult
from ingestion_pipelines.sirivm_otp_matching_function.models import (
    JourneyStopHistory,
    MatchedStop,
    PotentialMatch,
)

result = ProcessingResult(
    stop_pos_distances={},
    stop_pos_distances_remove=[],
    shard_stop_histories={
        "TLCT37812152024-08-20": JourneyStopHistory(
            last_match=45,
            last_avl_time=datetime(2024, 8, 20, 12, 0, 5, tzinfo=UTC),
            last_avl_index=236,
            matched_stops={
                1: MatchedStop(
                    last_match_time=datetime(
                        2024,
                        8,
                        20,
                        11,
                        28,
                        22,
                        tzinfo=UTC,
                    )
                ),
                2: MatchedStop(
                    last_match_time=datetime(
                        2024,
                        8,
                        20,
                        11,
                        30,
                        50,
                        tzinfo=UTC,
                    )
                ),
                3: MatchedStop(
                    last_match_time=datetime(
                        2024,
                        8,
                        20,
                        11,
                        31,
                        53,
                        tzinfo=UTC,
                    )
                ),
                4: MatchedStop(
                    last_match_time=datetime(
                        2024,
                        8,
                        20,
                        11,
                        32,
                        20,
                        tzinfo=UTC,
                    )
                ),
                5: MatchedStop(
                    last_match_time=datetime(
                        2024,
                        8,
                        20,
                        11,
                        32,
                        50,
                        tzinfo=UTC,
                    )
                ),
                6: MatchedStop(
                    last_match_time=datetime(
                        2024,
                        8,
                        20,
                        11,
                        34,
                        42,
                        tzinfo=UTC,
                    )
                ),
                7: MatchedStop(
                    last_match_time=datetime(
                        2024,
                        8,
                        20,
                        11,
                        35,
                        25,
                        tzinfo=UTC,
                    )
                ),
                8: MatchedStop(
                    last_match_time=datetime(
                        2024,
                        8,
                        20,
                        11,
                        35,
                        25,
                        tzinfo=UTC,
                    )
                ),
                9: MatchedStop(
                    last_match_time=datetime(
                        2024,
                        8,
                        20,
                        11,
                        36,
                        14,
                        tzinfo=UTC,
                    )
                ),
                10: MatchedStop(
                    last_match_time=datetime(
                        2024,
                        8,
                        20,
                        11,
                        36,
                        47,
                        tzinfo=UTC,
                    )
                ),
                11: MatchedStop(
                    last_match_time=datetime(
                        2024,
                        8,
                        20,
                        11,
                        36,
                        55,
                        tzinfo=UTC,
                    )
                ),
                12: MatchedStop(
                    last_match_time=datetime(
                        2024,
                        8,
                        20,
                        11,
                        37,
                        37,
                        tzinfo=UTC,
                    )
                ),
                13: MatchedStop(
                    last_match_time=datetime(
                        2024,
                        8,
                        20,
                        11,
                        37,
                        37,
                        tzinfo=UTC,
                    )
                ),
                15: MatchedStop(
                    last_match_time=datetime(
                        2024,
                        8,
                        20,
                        11,
                        38,
                        47,
                        tzinfo=UTC,
                    )
                ),
                16: MatchedStop(
                    last_match_time=datetime(
                        2024,
                        8,
                        20,
                        11,
                        39,
                        20,
                        tzinfo=UTC,
                    )
                ),
                19: MatchedStop(
                    last_match_time=datetime(
                        2024,
                        8,
                        20,
                        11,
                        40,
                        46,
                        tzinfo=UTC,
                    )
                ),
                20: MatchedStop(
                    last_match_time=datetime(
                        2024,
                        8,
                        20,
                        11,
                        41,
                        52,
                        tzinfo=UTC,
                    )
                ),
                21: MatchedStop(
                    last_match_time=datetime(2024, 8, 20, 11, 43, 8, tzinfo=UTC)
                ),
                22: MatchedStop(
                    last_match_time=datetime(2024, 8, 20, 11, 43, 8, tzinfo=UTC)
                ),
                24: MatchedStop(
                    last_match_time=datetime(
                        2024,
                        8,
                        20,
                        11,
                        43,
                        44,
                        tzinfo=UTC,
                    )
                ),
                25: MatchedStop(
                    last_match_time=datetime(
                        2024,
                        8,
                        20,
                        11,
                        44,
                        34,
                        tzinfo=UTC,
                    )
                ),
                26: MatchedStop(
                    last_match_time=datetime(
                        2024,
                        8,
                        20,
                        11,
                        46,
                        22,
                        tzinfo=UTC,
                    )
                ),
                27: MatchedStop(
                    last_match_time=datetime(
                        2024,
                        8,
                        20,
                        11,
                        46,
                        45,
                        tzinfo=UTC,
                    )
                ),
                28: MatchedStop(
                    last_match_time=datetime(
                        2024,
                        8,
                        20,
                        11,
                        46,
                        58,
                        tzinfo=UTC,
                    )
                ),
                29: MatchedStop(
                    last_match_time=datetime(
                        2024,
                        8,
                        20,
                        11,
                        47,
                        30,
                        tzinfo=UTC,
                    )
                ),
                30: MatchedStop(
                    last_match_time=datetime(
                        2024,
                        8,
                        20,
                        11,
                        48,
                        19,
                        tzinfo=UTC,
                    )
                ),
                31: MatchedStop(
                    last_match_time=datetime(
                        2024,
                        8,
                        20,
                        11,
                        48,
                        30,
                        tzinfo=UTC,
                    )
                ),
                33: MatchedStop(
                    last_match_time=datetime(
                        2024,
                        8,
                        20,
                        11,
                        50,
                        28,
                        tzinfo=UTC,
                    )
                ),
                34: MatchedStop(
                    last_match_time=datetime(
                        2024,
                        8,
                        20,
                        11,
                        51,
                        35,
                        tzinfo=UTC,
                    )
                ),
                35: MatchedStop(
                    last_match_time=datetime(2024, 8, 20, 11, 53, 8, tzinfo=UTC)
                ),
                36: MatchedStop(
                    last_match_time=datetime(2024, 8, 20, 11, 54, 9, tzinfo=UTC)
                ),
                37: MatchedStop(
                    last_match_time=datetime(
                        2024,
                        8,
                        20,
                        11,
                        54,
                        29,
                        tzinfo=UTC,
                    )
                ),
                39: MatchedStop(
                    last_match_time=datetime(
                        2024,
                        8,
                        20,
                        11,
                        55,
                        53,
                        tzinfo=UTC,
                    )
                ),
                40: MatchedStop(
                    last_match_time=datetime(
                        2024,
                        8,
                        20,
                        11,
                        57,
                        23,
                        tzinfo=UTC,
                    )
                ),
                41: MatchedStop(
                    last_match_time=datetime(2024, 8, 20, 11, 58, 3, tzinfo=UTC)
                ),
                42: MatchedStop(
                    last_match_time=datetime(
                        2024,
                        8,
                        20,
                        11,
                        58,
                        43,
                        tzinfo=UTC,
                    )
                ),
                43: MatchedStop(
                    last_match_time=datetime(2024, 8, 20, 11, 59, 5, tzinfo=UTC)
                ),
                44: MatchedStop(
                    last_match_time=datetime(
                        2024,
                        8,
                        20,
                        11,
                        59,
                        27,
                        tzinfo=UTC,
                    )
                ),
                45: MatchedStop(
                    last_match_time=datetime(
                        2024,
                        8,
                        20,
                        11,
                        59,
                        57,
                        tzinfo=UTC,
                    )
                ),
            },
            potential_matches={
                1: PotentialMatch(
                    last_avl_index=32,
                    last_distance=45.08752219926386,
                    last_time_in_zone=datetime(
                        2024,
                        8,
                        20,
                        11,
                        28,
                        22,
                        tzinfo=UTC,
                    ),
                )
            },
        )
    },
)