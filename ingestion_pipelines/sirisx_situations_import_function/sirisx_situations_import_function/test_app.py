from collections.abc import Generator
from datetime import UTC, date, datetime
from unittest.mock import MagicMock, patch

import pytest

from .models import SituationRecord


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch) -> None:  # noqa: ANN001 type not exported
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-2")


@pytest.fixture(autouse=True)
def mock_setup_db() -> Generator[MagicMock]:
    with patch(f"{__package__}.shared.db.setup_db") as mock_setup_db:
        mock_conn = MagicMock()
        mock_setup_db.return_value = mock_conn
        yield mock_conn


@pytest.fixture
def situation_record() -> SituationRecord:
    now = datetime.now(UTC)
    return SituationRecord(
        producer_ref="producer1",
        situation_number="abc-123",
        version="1",
        operator_noc="TST",
        line_name="5",
        direction="inbound",
        date_of_journey=now.date(),
        origin_departure_time=now,
        validity_start_date=now,
        validity_end_date=now,
        journey_code="VJ5",
        condition="cancelled",
        progress="closed",
        event_timestamp=now,
        creation_time=now,
    )


@patch(
    "ingestion_pipelines.sirisx_situations_import_function.sirisx_situations_import_function.app.ensure_db_connection",
)
@patch(
    "ingestion_pipelines.sirisx_situations_import_function.sirisx_situations_import_function.app.conn",
)
@patch(
    "ingestion_pipelines.sirisx_situations_import_function.sirisx_situations_import_function.app.insert_rows",
)
@patch(
    "ingestion_pipelines.sirisx_situations_import_function.sirisx_situations_import_function.app.parse_xml",
)
@patch(
    "ingestion_pipelines.sirisx_situations_import_function.sirisx_situations_import_function.app.requests.get",
)
def test_lambda_handler(
    mock_get: MagicMock,
    mock_parse_xml: MagicMock,
    mock_insert_rows: MagicMock,
    mock_conn: MagicMock,
    mock_ensure_db_connection: MagicMock,
    situation_record: SituationRecord,
) -> None:
    from .app import lambda_handler  # noqa: PLC0415,I001

    mock_ensure_db_connection.return_value= None
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    # Mock response from requests.get
    mock_response = MagicMock()
    mock_response.content = b"<siri-xs-xml>"
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    # Mock parse_xml function
    mock_parse_xml.return_value = [situation_record]

    lambda_handler({}, {})

    # Check expected calls
    mock_get.assert_called_once()
    mock_parse_xml.assert_called_once_with(b"<siri-xs-xml>")
    mock_insert_rows.assert_called_once_with(mock_cursor, [situation_record])


def test_parse_xml() -> None:
    from .app import NS_URI, parse_xml  # noqa: PLC0415,I001

    number_of_situation_elements = 2
    xml = f"""
    <Siri xmlns="{NS_URI}">
        <ServiceDelivery>
            <ResponseTimestamp>2025-04-25T11:00:00Z</ResponseTimestamp>
            <ProducerRef>DFT</ProducerRef>
            <SituationExchangeDelivery>
                <Situations>
                    <PtSituationElement>
                        <SituationNumber>abc-123</SituationNumber>
                        <Version>1</Version>
                        <OperatorRef>OpRef1</OperatorRef>
                        <PublishedLineName>10A</PublishedLineName>
                        <DirectionRef>inbound</DirectionRef>
                        <DatedVehicleJourneyRef>VJ1</DatedVehicleJourneyRef>
                        <Condition>cancelled</Condition>
                        <Progress>closed</Progress>
                        <ValidityPeriod>
                            <StartTime>2025-04-25T12:00:00Z</StartTime>
                            <EndTime>2025-04-25T14:00:00Z</EndTime>
                        </ValidityPeriod>
                        <OriginAimedDepartureTime>2025-04-25T12:30:00Z</OriginAimedDepartureTime>
                    </PtSituationElement>
                    <PtSituationElement>
                        <SituationNumber>abc-456</SituationNumber>
                        <Version>3</Version>
                        <OperatorRef>OpRef2</OperatorRef>
                        <PublishedLineName>25B</PublishedLineName>
                        <DirectionRef>outbound</DirectionRef>
                        <DatedVehicleJourneyRef>VJ2</DatedVehicleJourneyRef>
                        <Condition>normalService</Condition>
                        <Progress>open</Progress>
                        <ValidityPeriod>
                            <StartTime>2025-04-25T13:00:00Z</StartTime>
                            <EndTime>2025-04-25T15:00:00Z</EndTime>
                        </ValidityPeriod>
                        <OriginAimedDepartureTime>2025-04-25T13:45:00Z</OriginAimedDepartureTime>
                    </PtSituationElement>
                </Situations>
            </SituationExchangeDelivery>
        </ServiceDelivery>
    </Siri>
    """

    rows = parse_xml(xml.encode("utf-8"))

    assert len(rows) == number_of_situation_elements, "All PtSituationElements parsed"

    row1, row2 = rows

    assert isinstance(row1, SituationRecord)

    assert row1.producer_ref == "DFT"
    assert row1.situation_number == "abc-123"
    assert row1.version == "1"
    assert row1.operator_noc == "OpRef1"
    assert row1.line_name == "10A"
    assert row1.direction == "inbound"
    assert row1.date_of_journey == date(2025, 4, 25)
    assert row1.origin_departure_time == datetime(2025, 4, 25, 12, 30, 0, tzinfo=UTC)
    assert row1.validity_start_date == datetime(2025, 4, 25, 12, 0, 0, tzinfo=UTC)
    assert row1.validity_end_date == datetime(2025, 4, 25, 14, 0, 0, tzinfo=UTC)
    assert row1.journey_code == "VJ1"
    assert row1.condition == "cancelled"
    assert row1.progress == "closed"
    assert row1.event_timestamp == datetime(2025, 4, 25, 11, 0, 0, tzinfo=UTC)

    assert isinstance(row2, SituationRecord)
    assert row2.producer_ref == "DFT"
    assert row2.situation_number == "abc-456"
    assert row2.version == "3"
    assert row2.operator_noc == "OpRef2"
    assert row2.line_name == "25B"
    assert row2.direction == "outbound"
    assert row2.date_of_journey == date(2025, 4, 25)
    assert row2.origin_departure_time == datetime(2025, 4, 25, 13, 45, 0, tzinfo=UTC)
    assert row2.validity_start_date == datetime(2025, 4, 25, 13, 0, 0, tzinfo=UTC)
    assert row2.validity_end_date == datetime(2025, 4, 25, 15, 0, 0, tzinfo=UTC)
    assert row2.journey_code == "VJ2"
    assert row2.condition == "normalService"
    assert row2.progress == "open"
    assert row2.event_timestamp == datetime(2025, 4, 25, 11, 0, 0, tzinfo=UTC)


@patch(
    "ingestion_pipelines.sirisx_situations_import_function.sirisx_situations_import_function.app.conn",
)
@patch(
    "ingestion_pipelines.sirisx_situations_import_function.sirisx_situations_import_function.app.execute_batch",
)
def test_insert_rows(
    mock_execute_batch: MagicMock,
    mock_conn: MagicMock,
    situation_record: SituationRecord,
) -> None:
    from .app import insert_rows  # noqa: PLC0415,I001

    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    insert_rows(mock_conn, [situation_record])

    mock_execute_batch.assert_called_once()
    args, _ = mock_execute_batch.call_args

    assert len(args[2]) == 1, "One row inserted"
    assert isinstance(args[2][0], dict)
    assert args[2][0] == situation_record.to_dict(), "Inserted row matches given record"
