"""Database Functions"""

from os import environ
from pathlib import Path
from typing import Literal

import psycopg2.extras
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.parser import BaseModel
from psycopg2.extras import execute_values

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


def log_db_updated_row_count(
    entries_to_update: list,
    result: list,
) -> None:
    """Log the updated row counts"""
    if environ.get("LOG_DB_UPDATE_ROW_COUNT", "False") != "True":
        return
    entries_count = len(entries_to_update)
    result_count = len(result)
    if entries_count == result_count:
        logger.info(f"Updated all {result_count} rows")
    if entries_count > result_count:
        logger.warning(
            f"{result_count} out of {entries_count} rows has been updated.",
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
        entries_to_update: dict[str, dict[str, tuple]],
        entries_to_remove: list[tuple],
    ) -> None:
        """Update database to reflect successful live matching"""
        with self.connection.cursor() as cursor:
            if len(entries_to_remove) > 0:
                remove_result = execute_values(
                    cur=cursor,
                    sql=self.sql_queries.remove_live_matching,
                    argslist=entries_to_remove,
                    fetch=True,
                )
                log_db_updated_row_count(
                    entries_to_remove,
                    remove_result,
                )

            for match_index_dict in entries_to_update.values():
                if len(match_index_dict) > 0:
                    v_to_set = list(match_index_dict.values())
                    update_result = execute_values(
                        cur=cursor,
                        sql=self.sql_queries.set_live_matching,
                        argslist=v_to_set,
                        fetch=True,
                    )
                    log_db_updated_row_count(v_to_set, update_result)
            _update_batch_status(cursor, batch_id, "Success")

    @timer(logger)
    def historic_update_success(
        self,
        batch_id: int,
        entries_to_update: dict[str, dict[str, tuple]],
        entries_to_remove: list[tuple],
        avl_date_str: str,
    ) -> None:
        """Update database to reflect successful historic matching"""
        entries_to_remove_with_date = [
            (*entry, "".join(avl_date_str)) for entry in entries_to_remove
        ]
        with self.connection.cursor() as cursor:
            remove_result = execute_values(
                cur=cursor,
                sql=self.sql_queries.remove_historic_matching,
                argslist=entries_to_remove_with_date,
                fetch=True,
            )
            log_db_updated_row_count(
                entries_to_remove_with_date,
                remove_result,
            )

            for match_index_dict in entries_to_update.values():
                if len(match_index_dict) > 0:
                    v_to_set = match_index_dict.values()
                    v_to_set_with_date = [(*v, "".join(avl_date_str)) for v in v_to_set]
                    execute_values(
                        cursor,
                        self.sql_queries.set_historic_matching,
                        v_to_set_with_date,
                    )
                    # Update otp state again as the otp calculation is not taking the updated time difference value
                    update_result = execute_values(
                        cur=cursor,
                        sql=self.sql_queries.update_otp_state,
                        argslist=v_to_set_with_date,
                        fetch=True,
                    )
                    log_db_updated_row_count(
                        v_to_set_with_date,
                        update_result,
                    )

            _update_batch_status(
                cursor,
                batch_id,
                "Success",
            )
