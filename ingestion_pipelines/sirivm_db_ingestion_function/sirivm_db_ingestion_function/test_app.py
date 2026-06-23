from collections.abc import Generator
from unittest.mock import ANY, MagicMock, patch

import pytest
from aws_lambda_powertools.utilities.typing import LambdaContext

TEST_EVENT = {
    "Records": [
        {
            "messageAttributes": {
                "key": {"stringValue": "test-key"},
                "batch_id": {"stringValue": "batch123"},
            },
        },
    ],
}


@pytest.fixture(autouse=True)
def mock_env_vars(monkeypatch) -> None:  # noqa: ANN001 type not exported
    monkeypatch.setenv("SIRIVM_BUCKET", "test-bucket")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-2")


@pytest.fixture(autouse=True)
def mock_setup_db() -> Generator[MagicMock]:
    with patch(f"{__package__}.shared.db.setup_db") as mock_setup_db:
        mock_conn = MagicMock()
        mock_setup_db.return_value = mock_conn
        yield mock_conn


@patch(f"{__package__}.app.update_batch_status")
@patch(f"{__package__}.app.process_batch")
def test_lambda_handler_success(
    mock_process_batch: MagicMock,
    mock_update_batch_status: MagicMock,
) -> None:
    from .app import lambda_handler  # noqa: PLC0415,I001

    lambda_handler(TEST_EVENT, LambdaContext())

    # Assertions
    mock_update_batch_status.assert_any_call(
        ANY,
        "batch123",
        "Inprogress",
        ANY,
        None,
        "test-key",
    )
    mock_process_batch.assert_called_once_with(
        ANY,
        "test-bucket",
        "test-key",
        "batch123",
    )
    mock_update_batch_status.assert_any_call(
        ANY,
        "batch123",
        "Success",
        ANY,
        ANY,
        "test-key",
    )


@patch(f"{__package__}.app.update_batch_status")
@patch(f"{__package__}.app.process_batch")
def test_lambda_handler_error(
    mock_process_batch: MagicMock,
    mock_update_batch_status: MagicMock,
) -> None:
    from .app import lambda_handler  # noqa: PLC0415,I001

    mock_process_batch.side_effect = Exception("Something went wrong")

    with pytest.raises(Exception, match="Something went wrong"):
        lambda_handler(TEST_EVENT, LambdaContext())

    # Assertions
    mock_update_batch_status.assert_any_call(
        ANY,
        "batch123",
        "Inprogress",
        ANY,
        None,
        "test-key",
    )

    mock_update_batch_status.assert_any_call(
        ANY,
        "batch123",
        "Failed",
        ANY,
        ANY,
        "test-key",
    )


@pytest.mark.parametrize(
    ("status", "start_time", "end_time", "key", "expected_params"),
    [
        (
            "Inprogress",
            "2026-04-28T10:00:00",
            None,
            "test-key",
            [
                "Inprogress",
                "2026-04-28T10:00:00",
                None,
                "test-key",
                "batch123",
                "Inprogress",
                "2026-04-28T10:00:00",
                None,
                "test-key",
            ],
        ),
        (
            "Success",
            "2026-04-28T10:00:00",
            "2026-04-28T10:05:00",
            "test-key",
            [
                "Success",
                "2026-04-28T10:00:00",
                "2026-04-28T10:05:00",
                "test-key",
                "batch123",
                "Success",
                "2026-04-28T10:00:00",
                "2026-04-28T10:05:00",
                "test-key",
            ],
        ),
        (
            "Failed",
            "2026-04-28T10:00:00",
            "2026-04-28T10:05:00",
            "test-key",
            [
                "Failed",
                "2026-04-28T10:00:00",
                "2026-04-28T10:05:00",
                "test-key",
                "batch123",
                "Failed",
                "2026-04-28T10:00:00",
                "2026-04-28T10:05:00",
                "test-key",
            ],
        ),
    ],
)
def test_update_batch_status_uses_conditional_update(
    status: str,
    start_time: str,
    end_time: str | None,
    key: str,
    expected_params: list[object],
) -> None:
    from .app import update_batch_status  # noqa: PLC0415,I001

    mock_cursor = MagicMock()
    update_batch_status(
        mock_cursor,
        "batch123",
        status,
        start_time,
        end_time,
        key,
    )

    sql, params = mock_cursor.execute.call_args[0]

    assert "WHERE batch_id = %s" in sql
    assert "IS DISTINCT FROM" in sql
    assert params == expected_params
