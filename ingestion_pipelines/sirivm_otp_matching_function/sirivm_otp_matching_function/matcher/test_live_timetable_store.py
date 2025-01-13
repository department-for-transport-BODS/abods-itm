from datetime import date, timedelta

import pytest

from .live_timetable_store import LiveTimetableStore
from .models import AVLRecord, Route, Timetable, avl_group_id

avl = {
    "operator_ref": "TEST",
    "line_name": "10",
    "journey_ref": "20",
    "date_of_journey": "2024-12-25",
}
group_id = avl_group_id(avl)

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
    ("timetable", "avl_record", "expected_index", "expected_route"),
    [
        pytest.param(
            generic_timetable,
            {**avl, "direction_ref": "inbound"},
            group_id,
            generic_route,
            id="single journey for group id, returns journey data when passed correct direction",
        ),
        pytest.param(
            generic_timetable,
            {**avl, "direction_ref": "outbound"},
            group_id,
            generic_route,
            id="single journey for group id, returns journey data when passed different direction",
        ),
        pytest.param(
            generic_timetable,
            {**avl, "direction_ref": "random"},
            group_id,
            generic_route,
            id="single journey for group id, returns journey data when passed unknown direction",
        ),
        pytest.param(
            split_timetable,
            {**avl, "direction_ref": "inbound"},
            inbound_index,
            inbound_route,
            id="multiple journeys for group id, returns journey data corresponding to passed inbound direction",
        ),
        pytest.param(
            split_timetable,
            {**avl, "direction_ref": "outbound"},
            outbound_index,
            outbound_route,
            id="multiple journeys for group id, returns journey data corresponding to passed outbound direction",
        ),
        pytest.param(
            split_timetable,
            {**avl, "direction_ref": "random"},
            group_id + "|random",
            None,
            id="multiple journeys for group id, returns nothing when passed unknown direction",
        ),
        pytest.param(
            no_route_for_group_id,
            {**avl, "direction_ref": "outbound"},
            outbound_index,
            None,
            id="no journey data for group id returns nothing",
        ),
        pytest.param(
            generic_timetable,
            {
                **avl,
                "direction_ref": "inbound",
                "date_of_journey": (
                    date.fromisoformat(avl["date_of_journey"]) + timedelta(days=1)
                ).isoformat(),
            },
            group_id,
            generic_route,
            id="avl after midnight returns correct timetable",
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
