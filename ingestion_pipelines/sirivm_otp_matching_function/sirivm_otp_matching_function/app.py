from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, NotRequired, TypedDict

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.data_classes import SQSEvent
from aws_lambda_powertools.utilities.typing import LambdaContext
from dateutil.parser import parse
from shared.config import TIMETABLE_UPDATED_NOTIFICATION_SQS_KEY_VALUE

from .client_db import TimetableDBClient
from .client_s3 import TimetableS3Client
from .matcher.handle_stop_history import clean_stop_history
from .matcher.live_timetable_store import LiveTimetableStore
from .matcher.matching import match_avl_batch
from .matcher.models import LiveAVLRecord, Timetable
from .matcher.utils import timer

logger = Logger()

s3_client = TimetableS3Client()
db_client = TimetableDBClient()


class _Cache(TypedDict):
    main_timetable: NotRequired[Timetable]


_cache: _Cache = {}


@logger.inject_lambda_context(log_event=True)
@timer(logger)
def lambda_handler(event: dict[str, Any], _: LambdaContext) -> None:
    sqs_event = SQSEvent(event)

    for rec in sqs_event.records:
        with logger.append_context_keys(
            message_attributes={
                key: val.string_value for key, val in rec.message_attributes.items()
            },
            historic=False,
        ):
            # sirivm_timetable_s3_generation_function sends this message when done refreshing the extract
            if (
                rec.message_attributes["key"].string_value
                == TIMETABLE_UPDATED_NOTIFICATION_SQS_KEY_VALUE
            ):
                logger.info("Updating main timetable")
                _cache["main_timetable"] = s3_client.get_timetable_extract()
                continue

            if "main_timetable" not in _cache:
                logger.info("Fetching main timetable")
                _cache["main_timetable"] = s3_client.get_timetable_extract()

            logger.info("Processing live record")

            # Keys look something like this AVL/Processed/YYYY=2025/MM=02/DD=12/HH=15/avl_20250212150603.gz
            avl_file_key = rec.message_attributes["key"].string_value
            batch_id = int(rec.message_attributes["batch_id"].string_value)
            shard_no = rec.message_attributes["shard"].string_value

            # Check if avl file coming in order
            avl_file_time = avl_file_key[-17:-3]
            avl_file_datetime = parse(avl_file_time)

            with logger.append_context_keys(
                avl_file_time=avl_file_time,
                avl_datetime=avl_file_datetime,
            ):
                try:
                    shard_stop_history = s3_client.get_stop_history(shard_no)

                    clean_shard_stop_history = clean_stop_history(
                        shard_stop_history,
                        avl_file_datetime,
                    )

                    avl_list = s3_client.get_avl_data(avl_file_key, shard_no)
                    validate_avl_list(avl_list, batch_id)

                    to_set, to_remove, stop_history = match_avl_batch(
                        LiveTimetableStore(_cache["main_timetable"]),
                        avl_list,
                        clean_shard_stop_history,
                    )

                    db_client.live_update_success(
                        batch_id,
                        to_set,
                        to_remove,
                        datetime.now(UTC).date(),
                    )

                    s3_client.export_stop_history(stop_history, shard_no)

                    logger.info("Processing complete")
                except Exception:
                    logger.exception("An error occurred when processing the record")
                    db_client.batch_failed(batch_id)


def validate_avl_list(
    avl_list: Sequence[LiveAVLRecord],
    expected_batch_id: int,
) -> None:
    for avl in avl_list:
        if avl["batch_id"] != expected_batch_id:
            raise Exception("AVLs with multiple match ids retrieved")  # noqa: TRY002 - Not worth making an exception type
