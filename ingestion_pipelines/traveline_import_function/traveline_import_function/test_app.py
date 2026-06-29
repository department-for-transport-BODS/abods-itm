import importlib
from collections.abc import Generator
from unittest.mock import ANY, MagicMock, patch

import pytest

MOCK_NOC_CSV_DATA = [
    {
        "NOCCODE": "123",
        "PubNm": "Operator A",
        "Licence": "LIC123",
        "Mode": "Bus",
    },
    {
        "NOCCODE": "456",
        "PubNm": "Operator B",
        "Licence": "LIC456",
        "Mode": "Train",
    },
    {
        "NOCCODE": "789",
        "PubNm": "Operator C",
        "Licence": "LIC789",
        "Mode": "Ferry",
    },
]


@pytest.fixture(autouse=True)
def mock_setup_db() -> Generator[MagicMock]:
    db_module = importlib.import_module(f"{__package__}.shared.db")
    with patch.object(db_module, "setup_db") as mock_setup_db:
        mock_conn = MagicMock()
        mock_setup_db.return_value = mock_conn
        yield mock_conn


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch) -> None:  # noqa: ANN001 type not exported
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-2")
    monkeypatch.setenv("NOC_BUCKET_NAME", "test-bucket")
    monkeypatch.setenv("NOC_S3_KEY", "noc/prefix/")
    monkeypatch.setenv("NOC_BUCKET_REGION", "eu-west-2")
    monkeypatch.setenv("NOC_ROLE_ARN", "arn:aws:iam::123456789012:role/test-role")


@patch("petl.fromcsv")
@patch("psycopg2.extras.execute_values")
def test_lambda_handler(
    mock_execute_values: MagicMock,
    mock_fromcsv: MagicMock,
) -> None:
    from . import app  # noqa: PLC0415,I001

    mock_s3_client = MagicMock()
    mock_s3_client.get_object.return_value = {
        "Body": MagicMock(read=MagicMock(return_value=b"dummy csv data")),
    }

    mock_fromcsv.return_value.distinct.return_value.dicts.return_value = (
        MOCK_NOC_CSV_DATA
    )

    with (
        patch.object(app, "get_s3_client", return_value=mock_s3_client),
        patch.object(
            app,
            "resolve_noclines_key",
            return_value="noc/prefix/table_noclines_latest_csv.csv",
        ),
    ):
        app.lambda_handler({}, {})

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

    mock_s3_client.get_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="noc/prefix/table_noclines_latest_csv.csv",
    )
