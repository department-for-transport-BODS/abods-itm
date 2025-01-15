from collections.abc import Sequence
from datetime import datetime
from functools import lru_cache
from typing import Any, NotRequired, TypedDict

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.data_classes import SQSEvent
from aws_lambda_powertools.utilities.data_classes.sqs_event import SQSRecord
from aws_lambda_powertools.utilities.typing import LambdaContext
from dateutil.parser import parse

from .client_db import TimetableDBClient
from .client_s3 import TimetableS3Client, filter_avl_list
from .matcher.handle_stop_history import clean_stop_history
from .matcher.live_timetable_store import LiveTimetableStore
from .matcher.matching import match_avl_batch
from .matcher.models import LiveAVLRecord, Timetable
from .matcher.utils import timer
from .shards import shards

logger = Logger()

s3_client = TimetableS3Client()
db_client = TimetableDBClient()


@lru_cache(maxsize=1)
def read_timetable(timetable_name: str) -> Timetable:
    timetable = s3_client.download_timetable(timetable_name)
    logger.info(f"Loaded {timetable_name}")
    return timetable


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

        if "Historic" in rec.message_attributes:
            historic_record_handler(rec)
            continue

        # sirivm_timetable_s3_generation_function sends this message when done refreshing the extract
        if rec.message_attributes["key"].string_value == "timetable":
            logger.info("Updating main timetable")
            _cache["main_timetable"] = s3_client.download_main_timetable()
            continue

        if "main_timetable" not in _cache:
            logger.info("Fetching main timetable")
            _cache["main_timetable"] = s3_client.download_main_timetable()

        live_record_handler(rec, _cache["main_timetable"])


def historic_record_handler(rec: SQSRecord) -> None:
    """Fetch the historic AVL records and timetable to do historic OTP matching"""
    logger.append_keys(historic=True)
    logger.info("Processing historic record")

    fname = rec.message_attributes["key"].string_value
    shard_identifier = rec.message_attributes["shard"].string_value

    try:
        avl_time = fname[fname.index("avl_") + 4 : -3]
        avl_datetime = parse(avl_time)
        logger.append_keys(avl_time=avl_time, avl_datetime=avl_datetime)

        shard_stop_history, control_info = s3_client.get_stop_history(
            shard_identifier,
            int(avl_time),
        )

        # for recovery, only process avl file that is greater than last process avl file
        if int(avl_time) < int(control_info["last_avl"]):
            logger.info(
                "Record has already been processed, skipping",
                avl_time=avl_time,
                last_avl=control_info["last_avl"],
            )
            return

        clean_shard_stop_history = clean_stop_history(shard_stop_history, avl_datetime)

        avl_year = avl_datetime.year
        avl_month = str(avl_datetime.month).zfill(2)
        avl_day = str(avl_datetime.day).zfill(2)
        avl_hour = str(avl_datetime.hour).zfill(2)
        half_hour = 30
        avl_minute = "00" if avl_datetime.minute < half_hour else "30"
        timetable_key = f"timetable_shreds/YYYY={avl_year}/MM={avl_month}/DD={avl_day}/timetable_{avl_year}{avl_month}{avl_day}_{avl_hour}_{avl_minute}.json"
        logger.append_keys(timetable_key=timetable_key)
        timetable = read_timetable(timetable_key)

        avl_list = s3_client.get_avl_data(fname)
        avl_list = filter_avl_list(shard_identifier, shards, avl_list)
        batch_id = avl_list[0]["batch_id"]  # assuming we have at least one AVL
    except Exception:
        logger.exception("An error occurred when processing historic record")
        return
    try:
        validate_avl_list(avl_list, batch_id)

        to_set, to_remove, stop_history = match_avl_batch(
            LiveTimetableStore(timetable),
            avl_list,
            clean_shard_stop_history,
        )

        db_client.historic_update_success(
            batch_id,
            to_set,
            to_remove,
            f"{avl_year}-{avl_month}-{avl_day}",
        )

        s3_client.export_stop_history(
            stop_history,
            control_info,
            avl_datetime,
            shard_identifier,
        )

        logger.info("Processing complete")
    except Exception:
        logger.exception("An error occurred when processing historic record")
        db_client.batch_failed(batch_id)


def validate_avl_list(
    avl_list: Sequence[LiveAVLRecord],
    expected_batch_id: int,
) -> None:
    for avl in avl_list:
        if avl["batch_id"] != expected_batch_id:
            raise Exception("AVLs with multiple match ids retrieved")  # noqa: TRY002 - Not worth making an exception type


def live_record_handler(
    rec: SQSRecord,
    timetable: Timetable,
) -> None:
    """Fetch the live AVL records and timetable to do live OTP matching"""
    logger.append_keys(historic=False)
    logger.info("Processing live record")

    fname = rec.message_attributes["key"].string_value
    batch_id = int(rec.message_attributes["batch_id"].string_value)
    shard_identifier = rec.message_attributes["shard"].string_value

    try:
        # Check if avl file coming in in order
        avl_time_val = int(fname[-17:-3])
        avl_datetime = parse(str(avl_time_val))
        logger.append_keys(avl_time=avl_time_val, avl_datetime=avl_datetime)

        current_date = datetime.today()  # noqa: DTZ002 - Stop using today() later
        shard_stop_history, control_info = s3_client.get_stop_history(
            shard_identifier,
            avl_time_val,
        )

        clean_shard_stop_history = clean_stop_history(shard_stop_history, avl_datetime)

        avl_list = s3_client.get_avl_data(fname)
        avl_list = filter_avl_list(shard_identifier, shards, avl_list)
        validate_avl_list(avl_list, batch_id)

        to_set, to_remove, stop_history = match_avl_batch(
            LiveTimetableStore(timetable),
            avl_list,
            clean_shard_stop_history,
        )

        db_client.live_update_success(batch_id, to_set, to_remove)

        s3_client.export_stop_history(
            stop_history,
            control_info,
            current_date,
            shard_identifier,
        )

        logger.info("Processing complete")
    except Exception:
        logger.exception("An error occurred when processing the record")
        db_client.batch_failed(batch_id)
