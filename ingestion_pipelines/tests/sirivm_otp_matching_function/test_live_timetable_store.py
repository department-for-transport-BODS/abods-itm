import pytest

from ingestion_pipelines.sirivm_otp_matching_function.sirivm_otp_matching_function.matcher.live_timetable_store import (
    LiveTimetableStore,
)
from ingestion_pipelines.sirivm_otp_matching_function.sirivm_otp_matching_function.matcher.models import (
    RouteDetails,
    Timetable,
)

group_id = "test|10|20|2024-12-25"

generic_route = {"1": ((1.0, 1.0), "time", "timetable_id", "date")}
generic_timtetable = {group_id: generic_route}

inbound_direction = "inbound"
inbound_index = group_id + "|" + inbound_direction
inbound_route = {"1": ((1.0, 2.0), "time", "inbound_timetable_id", "date")}

outbound_direction = "outbound"
outbound_index = group_id + "|" + outbound_direction
outbound_route = {"2": ((2.0, 1.0), "time", "outbound_timetable_id", "date")}

split_timetable = {
    inbound_index: inbound_route,
    outbound_index: outbound_route,
}

no_route_for_avl = {"different_group_id": {}}


@pytest.mark.parametrize(
    ("timetable", "direction_ref", "expected_index", "expected_route"),
    [
        (generic_timtetable, "inbound", group_id, generic_route),
        (generic_timtetable, "outbound", group_id, generic_route),
        (split_timetable, "inbound", inbound_index, inbound_route),
        (split_timetable, "outbound", outbound_index, outbound_route),
        (no_route_for_avl, "inbound", inbound_index, None),
        (no_route_for_avl, "outbound", outbound_index, None),
    ],
)
def test_live_timetable_store(
    timetable: Timetable,
    direction_ref: str,
    expected_index: str,
    expected_route: RouteDetails,
):
    store = LiveTimetableStore(timetable)

    actual_index, actual_timetable = store.get_route_details(
        group_id=group_id,
        direction_ref=direction_ref,
    )

    assert actual_index == expected_index
    assert actual_timetable == expected_route
