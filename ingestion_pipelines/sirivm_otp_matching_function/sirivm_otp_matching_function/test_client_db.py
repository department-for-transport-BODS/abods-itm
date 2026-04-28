from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def mock_aws_region(monkeypatch) -> None:  # noqa: ANN001 type not exported
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-2")


@pytest.mark.parametrize("status", ["Success", "Failed"])
def test_update_batch_status_uses_conditional_update(status: str) -> None:
    from .client_db import _update_batch_status  # noqa: PLC0415,I001

    mock_cursor = MagicMock()
    _update_batch_status(mock_cursor, 123, status)

    sql, params = mock_cursor.execute.call_args[0]

    assert "WHERE batch_id = %s" in sql
    assert "otp_update_status IS DISTINCT FROM %s" in sql
    assert params == [status, 123, status]
