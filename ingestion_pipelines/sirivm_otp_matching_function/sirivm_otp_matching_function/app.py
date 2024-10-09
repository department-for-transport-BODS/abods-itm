from datetime import datetime
from functools import lru_cache
from typing import Any

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.data_classes import SQSEvent
from aws_lambda_powertools.utilities.data_classes.sqs_event import SQSRecord
from aws_lambda_powertools.utilities.typing import LambdaContext
from dateutil.parser import parse

from .client_db import TimetableDBClient
from .client_s3 import TimetableS3Client
from .matcher import clean_stop_history, positions_timetable_lookup
from .matcher.models import RouteDetails
from .matcher.utils import timer

logger = Logger()

s3_client = TimetableS3Client()
db_client = TimetableDBClient()


@lru_cache(maxsize=1)
def read_timetable(timetable_name: str) -> dict[str, RouteDetails]:
    timetable = s3_client.download_timetable(timetable_name)
    logger.info(f"Loaded {timetable_name}")
    return timetable


_cache = {}


@logger.inject_lambda_context(log_event=True, clear_state=True)
@timer(logger)
def lambda_handler(event: dict[str, Any], _: LambdaContext) -> None:
    sqs_event = SQSEvent(event)
    if "shards" not in _cache:
        _cache["shards"] = s3_client.get_shards()

    for rec in sqs_event.records:
        if "Historic" in rec.message_attributes:
            backfill_record_handler(rec, _cache["shards"])
            continue

        if rec.message_attributes["key"].string_value == "timetable":
            # Invalidate timetable cache, it will be when next needed
            # We probably want to switch to a time based TTL on the cache
            if "main_timetable" in _cache:
                del _cache["main_timetable"]

        if "main_timetable" not in _cache:
            _cache["main_timetable"] = s3_client.download_main_timetable()
        
        live_record_handler(rec, _cache["shards"], _cache["main_timetable"])


def backfill_record_handler(rec: SQSRecord, shards: dict[str, Any]) -> None:
    """Fetch the historic avl record and timetable to do historic otp matching"""
    try:
        fname = rec.message_attributes["key"].string_value
        shard_no = rec.message_attributes["shard"].string_value
        logger.info(f"OTP data being processed for file {fname}")
        batch_id = ""
        # find a timetable for matching
        avl_time = fname[fname.index("avl_") + 4 : -3]
        avl_datetime = parse(avl_time)
        avl_year = avl_datetime.year
        avl_month = str(avl_datetime.month).zfill(2)
        avl_day = str(avl_datetime.day).zfill(2)
        avl_date_str = f"{avl_year}-{avl_month}-{avl_day}"
        avl_hour = str(avl_datetime.hour).zfill(2)
        half_hour = 30
        avl_minute = "00" if avl_datetime.minute < half_hour else "30"
        timetable_dir = f"timetable_shreds/YYYY={avl_year}/MM={avl_month}/DD={avl_day}/"
        timetable_name = (
            f"timetable_{avl_year}{avl_month}{avl_day}_{avl_hour}_{avl_minute}.json"
        )
        timetable = read_timetable(timetable_dir + timetable_name)
        # fetch timetable s3
        shard_stop_history = s3_client.get_stop_history(
            avl_datetime,
            shard_no,
            int(avl_time),
        )

        # for recovery, only process avl file that is greater than last process avl file
        if int(avl_time) < int(shard_stop_history["control_info"]["last_avl"]):
            logger.info(f"{avl_time} has been processed, skipping.")
            return

        # clean stop history
        clean_shard_stop_history = clean_stop_history(shard_stop_history, avl_datetime)

        # fetch avl data
        avl_dict = s3_client.get_avl_data(fname)

        logger.info("Run matching")
        to_set, to_remove, stop_history = positions_timetable_lookup(
            timetable,
            shards,
            shard_no,
            avl_dict,
            None,
            clean_shard_stop_history,
        )
        db_client.historic_update_success(batch_id, to_set, to_remove, avl_date_str)
        logger.info(f"{fname} historic matching successful")
        s3_client.export_stop_history(stop_history, avl_datetime, shard_no)
        logger.info(f"OTP data updated for file {fname}")
    except Exception:
        logger.exception("An error occurred when processing backfill record")


def live_record_handler(
    rec: SQSRecord,
    shards: dict[str, Any],
    timetable: dict[str, Any],
) -> None:
    current_date = datetime.today()  # noqa: DTZ002 - Stop using today() later
    fname = rec.message_attributes["key"].string_value
    batch_id = rec.message_attributes["batch_id"].string_value
    shard_no = rec.message_attributes["shard"].string_value
    try:
        logger.info(f"OTP data being processed for file {fname}")
        # Check if avl file coming in in order
        avl_time_val = int(fname[-17:-3])
        avl_datetime = parse(str(avl_time_val))
        avl_dict = s3_client.get_avl_data(fname)
        # read stop history of the shard
        shard_stop_history = s3_client.get_stop_history(
            current_date,
            shard_no,
            avl_time_val,
        )
        # clean stop history
        clean_shard_stop_history = clean_stop_history(shard_stop_history, avl_datetime)

        to_set, to_remove, stop_history = positions_timetable_lookup(
            timetable,
            shards,
            shard_no,
            avl_dict,
            batch_id,
            clean_shard_stop_history,
        )
        db_client.live_update_success(batch_id, to_set, to_remove)
        s3_client.export_stop_history(stop_history, current_date, shard_no)
        logger.info(f"OTP data updated for file {fname}")

    except Exception:
        logger.exception("An error occurred when processing the record")
        db_client.batch_failed(batch_id)
