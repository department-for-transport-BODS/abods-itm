import polars as pl
import pytest

from ingestion_pipelines.sirivm_otp_matching_function.sirivm_otp_matching_function.matcher.historic_timetable_store import (
    HistoricTimetableStore,
)
from ingestion_pipelines.sirivm_otp_matching_function.sirivm_otp_matching_function.matcher.models import (
    RouteDetails,
)

timetable_df = pl.LazyFrame(
    {
        "group_id": [
            "fsrv|95|1225|2024-11-28",
            "fsrv|95|1225|2024-11-28",
            "fsrv|95|1225|2024-11-28",
            "scem|6|14|2024-11-28",
            "scem|6|14|2024-11-28",
        ],
        "stop_index": ["1", "2", "3", "1", "2"],
        "stop_latitude": [51.457073, 51.45738, 51.45921, 53.22627, 53.226276],
        "stop_longitude": [-2.1137395, -2.1162734, -2.1179187, -0.5378485, -0.5363951],
        "expected_departure_time": [
            "12:25:00",
            "12:26:00",
            "12:27:00",
            "11:03:00",
            "11:04:00",
        ],
        "timetable_id": [
            "2102152941",
            "2102153429",
            "2102153246",
            "2102152209",
            "2102152148",
        ],
        "date_of_journey": [
            "2024-11-28",
            "2024-11-28",
            "2024-11-28",
            "2024-11-28",
            "2024-11-28",
        ],
        "direction": ["outbound", "inbound", "inbound", "inbound", "inbound"],
    },
)

expected_route_details_1 = {
    "1": ((53.22627, -0.5378485), "11:03:00", "2102152209", "2024-11-28"),
    "2": ((53.226276, -0.5363951), "11:04:00", "2102152148", "2024-11-28"),
}

expected_route_details_2 = {
    "1": ((51.45738, -2.1162734), "12:26:00", "2102153429", "2024-11-28"),
    "2": ((51.45921, -2.1179187), "12:27:00", "2102153246", "2024-11-28"),
}


@pytest.mark.parametrize(
    (
        "group_id",
        "direction_ref",
        "expected_group_id",
        "expected_route_details",
    ),
    [
        pytest.param(
            "fsrv|95|1225|2024-11-28",
            "",
            "fsrv|95|1225|2024-11-28|",
            None,
            id="Empty direction input and there are two directions within one journey",
        ),
        pytest.param(
            "scem|6|14|2024-11-28",
            "inbound",
            "scem|6|14|2024-11-28",
            expected_route_details_1,
            id="With direction input and there is only one direction within one journey, the output group_id should not have direction",
        ),
        pytest.param(
            "fsrv|95|1225|2024-11-28",
            "inbound",
            "fsrv|95|1225|2024-11-28|inbound",
            expected_route_details_2,
            id="With inbound direction input and there are two directions within one journey, the output group_id should be with direction and the route details should only have inbound stop details",
        ),
    ],
)
def test_get_route_details(  # noqa: D102 - BODS-7131
    group_id: str,
    direction_ref: str,
    expected_group_id: str,
    expected_route_details: RouteDetails,
) -> tuple[str, RouteDetails]:
    test_timetable = HistoricTimetableStore(timetable_df)
    group_id, route_details = test_timetable.get_route_details(group_id, direction_ref)
    assert group_id == expected_group_id
    assert route_details == expected_route_details
