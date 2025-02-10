from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, NotRequired, TypedDict

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.data_classes import SQSEvent
from aws_lambda_powertools.utilities.typing import LambdaContext
from dateutil.parser import parse

from .client_db import TimetableDBClient
from .client_s3 import TimetableS3Client, filter_avl_list
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

    base_keys = set(logger.get_current_keys().keys())

    for rec in sqs_event.records:
        # Only needed if an event can have multiple records
        current_keys = set(logger.get_current_keys().keys())
        logger.remove_keys(current_keys - base_keys)

        logger.append_keys(
            message_attributes={
                key: val.string_value for key, val in rec.message_attributes.items()
            },
        )

        # sirivm_timetable_s3_generation_function sends this message when done refreshing the extract
        if rec.message_attributes["key"].string_value == "timetable":
            logger.info("Updating main timetable")
            _cache["main_timetable"] = s3_client.download_main_timetable()
            continue

        if "main_timetable" not in _cache:
            logger.info("Fetching main timetable")
            _cache["main_timetable"] = s3_client.download_main_timetable()

        logger.append_keys(historic=False)
        logger.info("Processing live record")

        fname = rec.message_attributes["key"].string_value
        batch_id = int(rec.message_attributes["batch_id"].string_value)
        shard_no = rec.message_attributes["shard"].string_value

        try:
            # Check if avl file coming in order
            avl_time_val = int(fname[-17:-3])
            avl_datetime = parse(str(avl_time_val))
            logger.append_keys(avl_time=avl_time_val, avl_datetime=avl_datetime)

            shard_stop_history = s3_client.get_stop_history(shard_no)

            clean_shard_stop_history = clean_stop_history(
                shard_stop_history,
                avl_datetime,
            )

            avl_list = s3_client.get_avl_data(fname)
            avl_list = list(filter_avl_list(shard_no, avl_list))
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
