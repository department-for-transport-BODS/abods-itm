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
generic_timetable = {group_id: generic_route}

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
no_route_for_group_id = {"different_group_id": outbound_route["2"]}


@pytest.mark.parametrize(
    ("timetable", "direction_ref", "expected_index", "expected_route"),
    [
        pytest.param(
            generic_timetable,
            "inbound",
            group_id,
            generic_route,
            id="single journey for group id, returns journey data when passed correct direction",
        ),
        pytest.param(
            generic_timetable,
            "outbound",
            group_id,
            generic_route,
            id="single journey for group id, returns journey data when passed different direction",
        ),
        pytest.param(
            generic_timetable,
            "random",
            group_id,
            generic_route,
            id="single journey for group id, returns journey data when passed unknown direction",
        ),
        pytest.param(
            split_timetable,
            "inbound",
            inbound_index,
            inbound_route,
            id="multiple journeys for group id, returns journey data corresponding to passed inbound direction",
        ),
        pytest.param(
            split_timetable,
            "outbound",
            outbound_index,
            outbound_route,
            id="multiple journeys for group id, returns journey data corresponding to passed outbound direction",
        ),
        pytest.param(
            split_timetable,
            "random",
            group_id + "|random",
            None,
            id="multiple journeys for group id, returns nothing when passed unknown direction",
        ),
        pytest.param(
            no_route_for_group_id,
            "outbound",
            outbound_index,
            None,
            id="no journey data for group id returns nothing",
        ),
    ],
)
def test_live_timetable_store(
    timetable: Timetable,
    direction_ref: str,
    expected_index: str,
    expected_route: RouteDetails,
) -> None:
    store = LiveTimetableStore(timetable)

    actual_index, actual_timetable = store.get_route_details(
        group_id=group_id,
        direction_ref=direction_ref,
    )

    assert actual_index == expected_index
    assert actual_timetable == expected_route
