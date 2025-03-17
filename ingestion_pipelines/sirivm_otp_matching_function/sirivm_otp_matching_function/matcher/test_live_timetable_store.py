import pytest

from .live_timetable_store import LiveTimetableStore
from .models import AVLRecord, Route, Timetable, avl_group_id

avl = {
    "recorded_at_time": "2025-03-17T12:58:25+00:00",
    "response_timestamp": "2025-03-17T13:01:49.311+00:00",
    "latitude": 51.321593,
    "longitude": -0.558455,
    "line_name": "81",
    "operator_ref": "SFGC",
    "vehicle_ref": "YX18KOD",
    "journey_ref": "622",
    "direction_ref": "inbound",
    "date_of_journey": "2025-03-17",
    "batch_id": 2607995,
}

# {"level": "WARNING", "location": "_get_timetable_by_index:43",
#  "message": "AVL is more than 4 hours before the start of a matching journey in the extract",
#  "timestamp": "2025-03-17 13:01:58,381+0000", "service": "sirivm_otp_matching_function",
#  "s3_bucket": "abods-sandbox-process-bucket", "cold_start": false,
#  "function_name": "abods-sandbox-sirivm-otp-matching-function6", "function_memory_size": "5000",
#  "function_arn": "arn:aws:lambda:eu-west-2:654654341097:function:abods-sandbox-sirivm-otp-matching-function6",
#  "function_request_id": "163b2f6b-6567-568c-967f-4f397a161c54",
#  "message_attributes": {"bucket": "abods-sandbox-process-bucket", "batch_id": "2607995", "shard": "5",
#                         "key": "AVL/Processed/YYYY=2025/MM=03/DD=17/HH=13/avl_20250317130153.gz"}, "historic": false,
#  "avl_time": "20250317130153", "avl_datetime": "2025-03-17 13:01:53",
#  "avl": {"recorded_at_time": "2025-03-17T12:58:25+00:00", "response_timestamp": "2025-03-17T13:01:49.311+00:00",
#          "latitude": 51.321593, "longitude": -0.558455, "line_name": "81", "operator_ref": "SFGC",
#          "vehicle_ref": "YX18KOD", "journey_ref": "622", "direction_ref": "inbound", "date_of_journey": "2025-03-17",
#          "batch_id": 2607995}, "group_id": "sfgc|81|622|2025-03-17", "stop_history_index": "sfgc|81|622|2025-03-17",
#  "timetable_index": "sfgc|3|319|2025-03-17", "start_of_journey": "2025-03-17 14:12:00+00:00",
#  "lower_bound": "2025-03-17 10:12:00+00:00", "xray_trace_id": "1-67d81d44-6f83da58b96c7a4bb9ec06bc"}
group_id = avl_group_id(avl)

generic_route = {"1": ((1.0, 1.0), "14:12:00", "timetable_id", "2025-03-17")}
generic_timetable = {group_id: generic_route}

inbound_direction = "inbound"
inbound_index = group_id + "|" + inbound_direction
inbound_route = {"1": ((1.0, 2.0), "12:00:00", "inbound_timetable_id", "2024-12-25")}

outbound_direction = "outbound"
outbound_index = group_id + "|" + outbound_direction
outbound_route = {"2": ((2.0, 1.0), "12:00:00", "outbound_timetable_id", "2024-12-25")}

split_timetable = {
    inbound_index: inbound_route,
    outbound_index: outbound_route,
}
no_route_for_group_id = {"different_group_id": outbound_route["2"]}


@pytest.mark.parametrize(
    ("timetable", "avl_record", "expected_index", "expected_route"),
    [
        pytest.param(
            generic_timetable,
            {**avl, "direction_ref": "inbound"},
            group_id,
            generic_route,
            id="single journey for group id, returns journey data when passed correct direction",
        ),
    ],
)
def test_live_timetable_store(
    timetable: Timetable,
    avl_record: AVLRecord,
    expected_index: str,
    expected_route: Route,
) -> None:
    store = LiveTimetableStore(timetable)

    actual_index, actual_timetable = store.get_route(avl_record)

    assert actual_index == expected_index
    assert actual_timetable == expected_route
