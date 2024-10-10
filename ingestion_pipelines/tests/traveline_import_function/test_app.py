from unittest.mock import ANY, MagicMock, patch

import pytest

MOCK_NOC_CSV_DATA = [
    {
        "NOCCODE": "123",
        "OperatorPublicName": "Operator A",
        "Licence": "LIC123",
        "Mode": "Bus",
    },
    {
        "NOCCODE": "456",
        "OperatorPublicName": "Operator B",
        "Licence": "LIC456",
        "Mode": "Train",
    },
    {
        "NOCCODE": "789",
        "OperatorPublicName": "Operator C",
        "Licence": "LIC789",
        "Mode": "Ferry",
    },
]


@pytest.fixture(autouse=True)
def mock_setup_db():
    with patch(
        "ingestion_pipelines.traveline_import_function.traveline_import_function.shared.db.setup_db",
    ) as mock_setup_db:
        mock_conn = MagicMock()
        mock_setup_db.return_value = mock_conn
        yield mock_conn


@patch("petl.fromcsv")
@patch("psycopg2.extras.execute_values")
def test_lambda_handler(mock_execute_values, mock_fromcsv):
    from ingestion_pipelines.traveline_import_function.traveline_import_function.app import (
        lambda_handler,
    )

    mock_fromcsv.return_value.distinct.return_value.dicts.return_value = (
        MOCK_NOC_CSV_DATA
    )

    lambda_handler({}, {})

    expected_rows = (
        ("123", "Operator A", "LIC123", "Bus"),
        ("456", "Operator B", "LIC456", "Train"),
        ("789", "Operator C", "LIC789", "Ferry"),
    )

    mock_execute_values.assert_called_once_with(
        ANY,
        ANY,
        expected_rows,
    )
