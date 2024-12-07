import polars as pl
import pytest

from ingestion_pipelines.sirivm_otp_matching_function.sirivm_otp_matching_function.matcher.historic_timetable_store import (
    HistoricTimetableStore,
)
from ingestion_pipelines.sirivm_otp_matching_function.sirivm_otp_matching_function.matcher.models import (
    RouteDetails,
    StopDetails,
)

group_id = "test|10|20|2024-12-25"
common_keys = {
    "group_id": group_id,
    "date_of_journey": "2024-12-25",
    "direction": "outbound",
}

generic_timetable = [
    {
        **common_keys,
        "stop_index": "1",
        "stop_latitude": 51.457073,
        "stop_longitude": -2.1137395,
        "expected_departure_time": "12:25:00",
        "timetable_id": "2102152941",
    },
    {
        **common_keys,
        "stop_index": "2",
        "stop_latitude": 51.45738,
        "stop_longitude": -2.1162734,
        "expected_departure_time": "12:26:00",
        "timetable_id": "2102153429",
    },
    {
        **common_keys,
        "stop_index": "3",
        "stop_latitude": 51.45921,
        "stop_longitude": -2.1179187,
        "expected_departure_time": "12:27:00",
        "timetable_id": "2102153246",
    },
]

split_timetable = [
    *generic_timetable,
    # Stop indexes below should be normalised for the matching logic
    {
        **common_keys,
        "direction": "inbound",
        "stop_index": "3",
        "stop_latitude": 53.22627,
        "stop_longitude": -0.5378485,
        "expected_departure_time": "12:25:00",
        "timetable_id": "2102152209",
    },
    {
        **common_keys,
        "direction": "inbound",
        "stop_index": "4",
        "stop_latitude": 53.226276,
        "stop_longitude": -0.5363951,
        "expected_departure_time": "12:26:00",
        "timetable_id": "2102152148",
    },
]
no_route_for_group_id = [{**generic_timetable[0], "group_id": "something random"}]


def to_stop_data(row: dict) -> StopDetails:
    return (
        (row["stop_latitude"], row["stop_longitude"]),
        row["expected_departure_time"],
        int(row["timetable_id"]),
        (row["date_of_journey"]),
    )


outbound_timetable = {
    "1": to_stop_data(generic_timetable[0]),
    "2": to_stop_data(generic_timetable[1]),
    "3": to_stop_data(generic_timetable[2]),
}
inbound_timetable = {
    "1": to_stop_data(split_timetable[3]),
    "2": to_stop_data(split_timetable[4]),
}


@pytest.mark.parametrize(
    (
        "timetable_data",
        "direction_ref",
        "expected_index",
        "expected_route_details",
    ),
    [
        pytest.param(
            generic_timetable,
            "outbound",
            f"{group_id}",
            outbound_timetable,
            id="single journey for group id, returns journey data when passed correct direction",
        ),
        pytest.param(
            generic_timetable,
            "inbound",
            f"{group_id}",
            outbound_timetable,
            id="single journey for group id, returns journey data when passed different direction",
        ),
        pytest.param(
            generic_timetable,
            "something random",
            f"{group_id}",
            outbound_timetable,
            id="single journey for group id, returns journey data when passed unknown direction",
        ),
        pytest.param(
            split_timetable,
            "outbound",
            f"{group_id}|outbound",
            outbound_timetable,
            id="multiple journeys for group id, returns journey data corresponding to passed outbound direction",
        ),
        pytest.param(
            split_timetable,
            "inbound",
            f"{group_id}|inbound",
            inbound_timetable,
            id="multiple journeys for group id, returns journey data corresponding to passed inbound direction",
        ),
        pytest.param(
            split_timetable,
            "random",
            f"{group_id}|random",
            None,
            id="multiple journeys for group id, returns nothing when passed unknown direction",
        ),
        pytest.param(
            no_route_for_group_id,
            "inbound",
            f"{group_id}|inbound",
            None,
            id="no journey data for group id returns nothing",
        ),
    ],
)
def test_get_route_details(
    timetable_data,
    direction_ref: str,
    expected_index: str,
    expected_route_details: RouteDetails | None,
):
    test_timetable = HistoricTimetableStore(pl.LazyFrame(timetable_data))
    stop_history_index, route_details = test_timetable.get_route_details(
        group_id,
        direction_ref,
    )
    assert stop_history_index == expected_index
    assert route_details == expected_route_details
