from datetime import datetime, UTC
from typing import Any

from aws_lambda_powertools import Logger

from .utils import timer

logger = Logger()


@timer(logger)
def clean_stop_history(
    stop_history: dict[str, dict[str, Any]],
    avl_datetime: datetime,
) -> dict:
    """
    Remove stop history which has the last avl time longer than an hour ago

    Args:
        stop_history (dict[str, dict[str, Any]]): Full stop history
        avl_datetime (datetime): Current avl record time

    Returns:
        dict: The stop history with the records within an hour of the avl time

    """
    remove_group_id = []
    for group_id, match_details in stop_history.items():
        if group_id != "control_info":
            last_avl_time_str = match_details["last_avl_time"][:19]
            avl_utc = avl_datetime.replace(tzinfo=UTC)
            last_avl_utc = datetime.strptime(
                last_avl_time_str,
                "%Y-%m-%d %H:%M:%S",
            ).replace(tzinfo=UTC)
            difference_in_seconds = (avl_utc - last_avl_utc).total_seconds()
            difference_in_hours = difference_in_seconds / 60 / 60
            if difference_in_hours > 1:
                logger.info(
                    f"Removing {group_id} with avl time {avl_utc} and last avl time {last_avl_utc}, time diff = {difference_in_hours}",
                )
                remove_group_id.append(group_id)
    for group_id in remove_group_id:
        del stop_history[group_id]
    return stop_history
