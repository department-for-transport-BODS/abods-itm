from datetime import UTC, datetime

from aws_lambda_powertools import Logger

from ..shared.config import TIMETABLE_EXTRACT_SLIDING_WINDOW_TIME_IN_MINUTES
from .models import StopHistory
from .utils import timer

logger = Logger()


@timer(logger)
def clean_stop_history(
    stop_history: StopHistory,
    avl_datetime: datetime,
) -> dict:
    """
    Remove stop history which has the last avl time longer than an hour ago

    Args:
        stop_history (StopHistory): Full stop history
        avl_datetime (datetime): Current avl record time

    Returns:
        dict: The stop history with the records within an hour of the avl time

    """
    cleaned: StopHistory = {}
    for group_id, match_details in stop_history.items():
        last_avl_time_str = match_details["last_avl_time"][:19]
        avl_utc = avl_datetime.replace(tzinfo=UTC)
        last_avl_utc = datetime.strptime(
            last_avl_time_str,
            "%Y-%m-%d %H:%M:%S",
        ).replace(tzinfo=UTC)
        difference_in_seconds = (avl_utc - last_avl_utc).total_seconds()
        difference_in_minutes = difference_in_seconds / 60
        if difference_in_minutes > TIMETABLE_EXTRACT_SLIDING_WINDOW_TIME_IN_MINUTES:
            logger.info(
                "Evicting group_id from stop_history",
                group_id=group_id,
                avl_utc=avl_utc,
                last_avl_utc=last_avl_utc,
                difference_in_minutes=difference_in_minutes,
            )
            continue

        cleaned[group_id] = match_details
    return cleaned
