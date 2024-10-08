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
def mock_env_vars(monkeypatch):
    monkeypatch.setenv("SIRIVM_BUCKET", "test-bucket")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-2")


@pytest.fixture(autouse=True)
def mock_setup_db():
    with patch("ingestion_pipelines.sirivm_db_ingestion_function.shared.db.setup_db") as mock_setup_db:
        mock_conn = MagicMock()
        mock_setup_db.return_value = mock_conn
        yield mock_conn


@patch("ingestion_pipelines.sirivm_db_ingestion_function.app.update_batch_status")
@patch("ingestion_pipelines.sirivm_db_ingestion_function.app.process_batch")
def test_lambda_handler_success(
    mock_process_batch,
    mock_update_batch_status,
):
    from ingestion_pipelines.sirivm_db_ingestion_function.app import lambda_handler

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


@patch("ingestion_pipelines.sirivm_db_ingestion_function.app.update_batch_status")
@patch("ingestion_pipelines.sirivm_db_ingestion_function.app.process_batch")
def test_lambda_handler_error(
    mock_process_batch,
    mock_update_batch_status,
):
    from ingestion_pipelines.sirivm_db_ingestion_function.app import lambda_handler

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
