"""Bus starting early"""

import datetime

from ..util import run_historic_matching_test

matches = [
    {
        "stop_index": "1",
        "time_difference": 21.0,
        "last_time_in_zone_str": "08:00:21",
        "timetable_id": 3746244226,
        "last_time_in_zone": datetime.datetime(
            2025, 6, 18, 8, 0, 21, tzinfo=datetime.UTC
        ),
        "timestamp_after_estimate": None,
        "otp_state": "OnTime",
        "stop_type": "Non-final",
    },
    {
        "stop_index": "2",
        "time_difference": 38.0,
        "last_time_in_zone_str": "08:02:38",
        "timetable_id": 3746244227,
        "last_time_in_zone": datetime.datetime(
            2025, 6, 18, 8, 2, 38, tzinfo=datetime.UTC
        ),
        "timestamp_after_estimate": None,
        "otp_state": "OnTime",
        "stop_type": "Non-final",
    },
    {
        "stop_index": "3",
        "time_difference": -15.0,
        "last_time_in_zone_str": "08:03:45",
        "timetable_id": 3746244228,
        "last_time_in_zone": datetime.datetime(
            2025, 6, 18, 8, 3, 45, tzinfo=datetime.UTC
        ),
        "timestamp_after_estimate": None,
        "otp_state": "OnTime",
        "stop_type": "Non-final",
    },
    {
        "stop_index": "4",
        "time_difference": 91.0,
        "last_time_in_zone_str": "08:05:31",
        "timetable_id": 3746244229,
        "last_time_in_zone": datetime.datetime(
            2025, 6, 18, 8, 5, 31, tzinfo=datetime.UTC
        ),
        "timestamp_after_estimate": None,
        "otp_state": "OnTime",
        "stop_type": "Non-final",
    },
    {
        "stop_index": "5",
        "time_difference": 7.0,
        "last_time_in_zone_str": "08:08:07",
        "timetable_id": 3746244230,
        "last_time_in_zone": datetime.datetime(
            2025, 6, 18, 8, 8, 7, tzinfo=datetime.UTC
        ),
        "timestamp_after_estimate": None,
        "otp_state": "OnTime",
        "stop_type": "Non-final",
    },
    {
        "stop_index": "6",
        "time_difference": -8.0,
        "last_time_in_zone_str": "08:11:52",
        "timetable_id": 3746244231,
        "last_time_in_zone": datetime.datetime(
            2025, 6, 18, 8, 11, 52, tzinfo=datetime.UTC
        ),
        "timestamp_after_estimate": None,
        "otp_state": "OnTime",
        "stop_type": "Non-final",
    },
    {
        "stop_index": "7",
        "time_difference": 39.0,
        "last_time_in_zone_str": "08:26:39",
        "timetable_id": 3746244232,
        "last_time_in_zone": datetime.datetime(
            2025, 6, 18, 8, 26, 39, tzinfo=datetime.UTC
        ),
        "timestamp_after_estimate": None,
        "otp_state": "OnTime",
        "stop_type": "Non-final",
    },
    {
        "stop_index": "8",
        "time_difference": 276.0,
        "last_time_in_zone_str": "08:30:36",
        "timetable_id": 3746244233,
        "last_time_in_zone": datetime.datetime(
            2025, 6, 18, 8, 30, 36, tzinfo=datetime.UTC
        ),
        "timestamp_after_estimate": None,
        "otp_state": "OnTime",
        "stop_type": "Non-final",
    },
    {
        "stop_index": "9",
        "time_difference": 115.0,
        "last_time_in_zone_str": "08:30:55",
        "timetable_id": 3746244234,
        "last_time_in_zone": datetime.datetime(
            2025, 6, 18, 8, 30, 55, tzinfo=datetime.UTC
        ),
        "timestamp_after_estimate": None,
        "otp_state": "OnTime",
        "stop_type": "Non-final",
    },
    {
        "stop_index": "10",
        "time_difference": -28.0,
        "last_time_in_zone_str": "08:32:32",
        "timetable_id": 3746244235,
        "last_time_in_zone": datetime.datetime(
            2025, 6, 18, 8, 32, 32, tzinfo=datetime.UTC
        ),
        "timestamp_after_estimate": None,
        "otp_state": "OnTime",
        "stop_type": "final",
    },
]


def test_historic_match() -> None:
    assert run_historic_matching_test(__file__) == matches
