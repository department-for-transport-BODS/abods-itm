from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def mock_aws_region(monkeypatch) -> None:  # noqa: ANN001 type not exported
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-2")


@pytest.mark.parametrize(
    ("status", "end_time", "key", "expected_params"),
    [
        (
            "Success",
            "2026-04-28 10:00:00.000000",
            "incoming-key",
            [
                "Success",
                "2026-04-28 10:00:00.000000",
                "incoming-key",
                123,
                "Success",
                "2026-04-28 10:00:00.000000",
                "incoming-key",
                "incoming-key",
            ],
        ),
        (
            "Failed",
            "2026-04-28 10:05:00.000000",
            "incoming-key",
            [
                "Failed",
                "2026-04-28 10:05:00.000000",
                "incoming-key",
                123,
                "Failed",
                "2026-04-28 10:05:00.000000",
                "incoming-key",
                "incoming-key",
            ],
        ),
        (
            "Failed",
            "2026-04-28 10:05:00.000000",
            None,
            [
                "Failed",
                "2026-04-28 10:05:00.000000",
                None,
                123,
                "Failed",
                "2026-04-28 10:05:00.000000",
                None,
                None,
            ],
        ),
    ],
)
def test_update_s3_ingestion_status_uses_conditional_update(
    status: str,
    end_time: str,
    key: str | None,
    expected_params: list[object],
) -> None:
    from .app import update_s3_ingestion_status  # noqa: PLC0415,I001

    mock_cursor = MagicMock()
    update_s3_ingestion_status(
        mock_cursor,
        123,
        status,
        end_time,
        key,
    )

    sql, params = mock_cursor.execute.call_args[0]

    assert "WHERE batch_id = %s" in sql
    assert "IS DISTINCT FROM" in sql
    assert "COALESCE(%s, s3_avl_gip_key)" in sql
    assert params == expected_params
