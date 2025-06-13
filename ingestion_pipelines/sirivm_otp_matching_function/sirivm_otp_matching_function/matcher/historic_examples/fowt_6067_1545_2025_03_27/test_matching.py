"""Route with avl pings greater than 60 seconds"""

import datetime

from ..util import run_historic_matching_test

matches = [
    {
        "stop_index": "1",
        "time_difference": -180.0,
        "last_time_in_zone_str": "15:42:00",
        "timetable_id": 3109256886,
        "last_time_in_zone": datetime.datetime(
            2025, 3, 27, 15, 42, tzinfo=datetime.UTC,
        ),
        "timestamp_after_estimate": None,
        "otp_state": "Early",
        "stop_type": "Non-final",
    },
    {
        "stop_index": "4",
        "time_difference": -15.0,
        "last_time_in_zone_str": "15:53:45",
        "timetable_id": 3109256889,
        "last_time_in_zone": datetime.datetime(
            2025, 3, 27, 15, 53, 45, tzinfo=datetime.UTC,
        ),
        "timestamp_after_estimate": None,
        "otp_state": "OnTime",
        "stop_type": "Non-final",
    },
    {
        "stop_index": "7",
        "time_difference": -51.0,
        "last_time_in_zone_str": "15:55:09",
        "timetable_id": 3109256892,
        "last_time_in_zone": datetime.datetime(
            2025, 3, 27, 15, 55, 9, tzinfo=datetime.UTC,
        ),
        "timestamp_after_estimate": None,
        "otp_state": "OnTime",
        "stop_type": "Non-final",
    },
    {
        "stop_index": "8",
        "time_difference": 128.0,
        "last_time_in_zone_str": None,
        "timetable_id": 3109256893,
        "last_time_in_zone": None,
        "timestamp_after_estimate": datetime.datetime(
            2025, 3, 27, 16, 2, 8, tzinfo=datetime.UTC,
        ),
        "otp_state": "OnTime",
        "stop_type": "Non-final",
    },
    {
        "stop_index": "9",
        "time_difference": -161.0,
        "last_time_in_zone_str": None,
        "timetable_id": 3109256894,
        "last_time_in_zone": None,
        "timestamp_after_estimate": datetime.datetime(
            2025, 3, 27, 16, 2, 19, tzinfo=datetime.UTC,
        ),
        "otp_state": "Early",
        "stop_type": "Non-final",
    },
    {
        "stop_index": "10",
        "time_difference": -541.0,
        "last_time_in_zone_str": "16:04:59",
        "timetable_id": 3109256895,
        "last_time_in_zone": datetime.datetime(
            2025, 3, 27, 16, 4, 59, tzinfo=datetime.UTC,
        ),
        "timestamp_after_estimate": None,
        "otp_state": "Early",
        "stop_type": "Non-final",
    },
    {
        "stop_index": "11",
        "time_difference": -518.0,
        "last_time_in_zone_str": "16:06:22",
        "timetable_id": 3109256896,
        "last_time_in_zone": datetime.datetime(
            2025, 3, 27, 16, 6, 22, tzinfo=datetime.UTC,
        ),
        "timestamp_after_estimate": None,
        "otp_state": "Early",
        "stop_type": "Non-final",
    },
    {
        "stop_index": "12",
        "time_difference": -662.0,
        "last_time_in_zone_str": "16:15:58",
        "timetable_id": 3109256897,
        "last_time_in_zone": datetime.datetime(
            2025, 3, 27, 16, 15, 58, tzinfo=datetime.UTC,
        ),
        "timestamp_after_estimate": None,
        "otp_state": "Early",
        "stop_type": "Non-final",
    },
    {
        "stop_index": "13",
        "time_difference": -777.0,
        "last_time_in_zone_str": "16:17:03",
        "timetable_id": 3109256898,
        "last_time_in_zone": datetime.datetime(
            2025, 3, 27, 16, 17, 3, tzinfo=datetime.UTC,
        ),
        "timestamp_after_estimate": None,
        "otp_state": "Early",
        "stop_type": "Non-final",
    },
    {
        "stop_index": "14",
        "time_difference": -934.0,
        "last_time_in_zone_str": "16:19:26",
        "timetable_id": 3109256899,
        "last_time_in_zone": datetime.datetime(
            2025, 3, 27, 16, 19, 26, tzinfo=datetime.UTC,
        ),
        "timestamp_after_estimate": None,
        "otp_state": "Early",
        "stop_type": "Non-final",
    },
    {
        "stop_index": "15",
        "time_difference": -1347.0,
        "last_time_in_zone_str": "16:23:33",
        "timetable_id": 3109256900,
        "last_time_in_zone": datetime.datetime(
            2025, 3, 27, 16, 23, 33, tzinfo=datetime.UTC,
        ),
        "timestamp_after_estimate": None,
        "otp_state": "Early",
        "stop_type": "Non-final",
    },
]


def test_historic_match() -> None:
    assert run_historic_matching_test(__file__) == matches
