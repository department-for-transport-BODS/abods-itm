# import pytest
# import os
# import logging
# from unittest import mock
# from ingestion_pipelines.sirivm_otp_matching_function.sirivm_otp_matching_function.matcher.utils import log_specific

# @pytest.fixture(autouse=True)
# def mock_settings_env_vars():
#     with mock.patch.dict(os.environ, {"AWSREGION": "eu-west-2", "POSTGRES_HOST": "abods-sandbox", "POSTGRES_PORT": "123", "POSTGRES_USER": "rw", "POSTGRES_DB": "db", "OPERATOR_REF": "TFLO", "LINE_NAME": "1", "SIRIVM_BUCKET": "sandbox"}):
#         yield

# @pytest.mark.parametrize(
#     "avl_operator_ref, avl_line_name, log_message, log_type",
#     [
#         pytest.param(
#             "TFLO", "1", "stop 1 matched", None, id="operator ref and line name matched, there's a log message"
#         ),
#         pytest.param(
#             "FSMR", "1", "stop 2 matched", None, id="operator ref not matched but line name matched, no log message"
#         ),
#         pytest.param(
#             "FSMR", "2", "stop 2 matched", None, id="operator ref and line name not matched, no log message"
#         ),
#     ],
# )
# def test_log_specific(avl_operator_ref: str, avl_line_name: str, log_message: str, log_type=None):
#     # arrange
#     operator_ref = "TFLO"
#     line_name = "1"
#     test_log_message = "stop 1 matched"

#     logger = logging.getLogger('sirivm')
#     logger.propagate=True

#     # act
#     with caplog.at_level(logging.INFO):
#         log_specific(avl_operator_ref, avl_line_name, "stop 1 matched")
    
#     # assert
#     assert "stop 1 matched" in caplog.text