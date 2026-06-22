from collections.abc import Generator
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
def mock_setup_db() -> Generator[MagicMock]:
    with patch(
        f"{__package__}.shared.db.setup_db",
    ) as mock_setup_db:
        mock_conn = MagicMock()
        mock_setup_db.return_value = mock_conn
        yield mock_conn


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch) -> None:  # noqa: ANN001 type not exported
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-2")
    monkeypatch.setenv("NOC_BUCKET_NAME", "test-bucket")
    monkeypatch.setenv("NOC_S3_KEY", "test/prefix/")
    monkeypatch.setenv("NOC_BUCKET_REGION", "eu-west-2")
    monkeypatch.setenv("NOC_ROLE_ARN", "arn:aws:iam::123456789012:role/test-role")


@patch(f"{__package__}.app.get_s3_client")
@patch("petl.fromcsv")
@patch("psycopg2.extras.execute_values")
def test_lambda_handler(mock_execute_values, mock_fromcsv, mock_get_s3_client):
    mock_s3 = MagicMock()
    mock_get_s3_client.return_value = mock_s3
    mock_s3.get_paginator.return_value.paginate.return_value = [
        {
            "Contents": [
                {
                    "Key": "test/prefix/table_noclines_latest_csv.csv",
                    "LastModified": ANY,
                }
            ]
        }
    ]

    mock_fromcsv.return_value.distinct.return_value.dicts.return_value = MOCK_NOC_CSV_DATA

    from .app import lambda_handler
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
        page_size=5000,
    )