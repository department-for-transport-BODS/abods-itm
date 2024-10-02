"""Database Functions"""

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Literal

import psycopg2.extras
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.parser import BaseModel
from psycopg2.extras import execute_values

from .matcher.models import MatchedStopDetails, RecordToRemove
from .matcher.utils import timer
from .shared.db import setup_db

logger = Logger()


class SQLQueries(BaseModel):
    """SQL data loaded from file"""

    set_live_matching: str
    set_historic_matching: str
    remove_live_matching: str
    remove_historic_matching: str
    update_otp_state: str


def _load_sql_queries() -> SQLQueries:
    current_file = Path(__file__).resolve()
    sql_dir = current_file.parent / "sql"

    def read_sql_file(filename: str) -> str:
        file_path = sql_dir / filename
        return file_path.read_text()

    return SQLQueries(
        set_live_matching=read_sql_file("set_live_matching.sql"),
        set_historic_matching=read_sql_file("set_historic_matching.sql"),
        remove_live_matching=read_sql_file("remove_live_matching.sql"),
        remove_historic_matching=read_sql_file("remove_historic_matching.sql"),
        update_otp_state=read_sql_file("update_otp_state.sql"),
    )


def _update_batch_status(
    cursor: psycopg2.extensions.cursor,
    batch_id: int | None,
    status: Literal["Success", "Failed"],
) -> None:
    """Update the OTP update status for a specific batch"""
    cursor.execute(
        "UPDATE public.batch SET otp_update_status = %s WHERE batch_id = %s;",
        [status, batch_id],
    )


class TimetableDBClient:
    """Client for interacting with database"""

    def __init__(self) -> None:
        """Construct a client"""
        self.sql_queries = _load_sql_queries()
        self.connection = setup_db()

    @timer(logger)
    def batch_failed(self, batch_id: int) -> None:
        """Update database to reflect failed matching"""
        with self.connection.cursor() as cursor:
            _update_batch_status(cursor, batch_id, "Failed")

    @timer(logger)
    def live_update_success(
        self,
        batch_id: int,
        entries_to_update: Sequence[MatchedStopDetails],
        entries_to_remove: Sequence[RecordToRemove],
    ) -> None:
        """Update database to reflect successful live matching"""
        entries_to_remove_with_date = [
            (entry.stop_index, entry.stop_details.timetable_id, entry.avl.group_id)
            for entry in entries_to_remove
        ]
        grouped = _prepare_new_entries(entries_to_update)
        with self.connection.cursor() as cursor:
            if len(entries_to_remove) > 0:
                execute_values(
                    cursor,
                    self.sql_queries.remove_live_matching,
                    entries_to_remove_with_date,
                )

            for group_id, records in grouped.items():
                values = [
                    (
                        record.get_time_difference(),
                        str(record.last_time_in_zone.strftime("%H:%M:%S")),
                        record.stop_details.timetable_id,
                        record.avl.group_id,
                        record.batch_id,
                        record.last_time_in_zone,
                        record.get_otp_state(),
                        "final" if record.is_final_stop else "Non-final",
                    )
                    for record in records
                ]
                execute_values(
                    cursor,
                    self.sql_queries.set_live_matching,
                    values,
                )

            _update_batch_status(cursor, batch_id, "Success")

    @timer(logger)
    def historic_update_success(
        self,
        entries_to_update: Sequence[MatchedStopDetails],
        entries_to_remove: Sequence[RecordToRemove],
        avl_date_str: str,
    ) -> None:
        """Update database to reflect successful historic matching"""
        entries_to_remove_with_date = [
            (
                entry.stop_index,
                entry.stop_details.timetable_id,
                entry.avl.group_id,
                avl_date_str,
            )
            for entry in entries_to_remove
        ]
        grouped = _prepare_new_entries(entries_to_update)
        with self.connection.cursor() as cursor:
            if len(entries_to_remove) > 0:
                execute_values(
                    cursor,
                    self.sql_queries.remove_historic_matching,
                    entries_to_remove_with_date,
                )

            for group_id, records in grouped.items():
                values = [
                    (
                        record.get_time_difference(),
                        str(record.last_time_in_zone.strftime("%H:%M:%S")),
                        record.stop_details.timetable_id,
                        record.avl.group_id,
                        record.batch_id,
                        record.last_time_in_zone,
                        record.get_otp_state(),
                        "final" if record.is_final_stop else "Non-final",
                        avl_date_str,
                    )
                    for record in records
                ]
                execute_values(
                    cursor,
                    self.sql_queries.set_historic_matching,
                    values,
                )
                # Update otp state again as the otp calculation is not taking the updated time difference value
                execute_values(
                    cursor,
                    self.sql_queries.update_otp_state,
                    values,
                )

            _update_batch_status(
                cursor,
                None,  # Always update same record for debugging
                "Success",
            )


def _prepare_new_entries(
    entries_to_update: Sequence[MatchedStopDetails],
) -> Mapping[str, Sequence[MatchedStopDetails]]:
    # deduplicate any pm_index entries for the same group
    grouped = {}
    for entry in entries_to_update:
        grouped.setdefault(entry.avl.group_id, {})[entry.stop_index] = entry

    # flatten by group id
    by_group_id = {}
    for group_id, match_index_dict in grouped.items():
        by_group_id[group_id] = list(match_index_dict.values())

    return by_group_id
