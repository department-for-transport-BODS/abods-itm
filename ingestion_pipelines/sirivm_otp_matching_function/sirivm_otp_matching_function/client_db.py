"""
Database Functions
"""

import os
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Literal, ParamSpec, TypeVar

import boto3
import psycopg2.extras
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.parser import BaseModel, ValidationError
from botocore.exceptions import TokenRetrievalError
from psycopg2.extras import execute_values

from .matcher.utils import timer

logger = Logger()

Param = ParamSpec("Param")
Return = TypeVar("Return")


def db_exception_handler(func: Callable[Param, Return]) -> Callable[Param, Return]:
    """
    Exception handler for database query errors
    """

    @wraps(func)
    def wrapper(*args: Param.args, **kwargs: Param.kwargs) -> Return:
        try:
            return func(*args, **kwargs)
        except psycopg2.Error as e:
            logger.error("Database error during %s: %s", func.__name__, str(e))
            raise

    return wrapper


class DBConfig(BaseModel):
    """
    Database Config
    """

    region: str
    host: str
    port: int
    user: str
    database: str


class SQLQueries(BaseModel):
    """
    SQL data loaded from file
    """

    set_live_matching: str
    set_historic_matching: str
    remove_live_matching: str
    remove_historic_matching: str
    update_otp_state: str


def load_sql_queries() -> SQLQueries:
    """
    Load SQL Queries from file
    """
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


def get_rds_config():
    """
    Get RDS Config
    """
    try:
        config = DBConfig(
            region=os.environ["AWS_REGION"],
            host=os.environ["POSTGRES_HOST"],
            port=int(os.environ["POSTGRES_PORT"]),
            user=os.environ["POSTGRES_USER"],
            database=os.environ["POSTGRES_DB"],
        )
    except (ValidationError, ValueError) as exc:
        raise ValueError("Missing Database Configuration Values") from exc
    return config


class TimetableDBClient:
    """
    Client for interacting with database
    """

    def __init__(self):
        self.conf = self._get_rds_config()
        self.sql_queries = self._load_sql_queries()
        self.cursor = self._create_db_cursor()

    def _get_rds_config(self) -> DBConfig:
        try:
            return DBConfig(
                region=os.environ["AWS_REGION"],
                host=os.environ["POSTGRES_HOST"],
                port=int(os.environ["POSTGRES_PORT"]),
                user=os.environ["POSTGRES_USER"],
                database=os.environ["POSTGRES_DB"],
            )
        except (ValidationError, ValueError) as exc:
            raise ValueError("Missing Database Configuration Values") from exc

    def _load_sql_queries(self) -> SQLQueries:
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

    def _get_rds_token(self) -> str:
        session = boto3.Session()
        client = session.client("rds")

        try:
            token = client.generate_db_auth_token(
                DBHostname=self.conf.host,
                Port=self.conf.port,
                Region=self.conf.region,
                DBUsername=self.conf.user,
            )
            return token
        except TokenRetrievalError as e:
            logger.error("Could not get RDS Token %s", e)
            raise ValueError("Could not get RDS Token") from e

    def _create_db_cursor(self):
        conn = psycopg2.connect(
            host=self.conf.host,
            port=self.conf.port,
            database=self.conf.database,
            user=self.conf.user,
            password=self._get_rds_token(),
            sslmode="require",
        )
        conn.autocommit = True
        cur = conn.cursor()
        return cur

    @db_exception_handler
    def _update_live_timetable(self, entries_to_update: dict[str, dict[str, Any]]):
        """
        Update Timetable Data
        """
        if len(entries_to_update) > 0:
            for group_id, match_index_dict in entries_to_update.items():
                if len(match_index_dict) > 0:
                    v_to_set = list(match_index_dict.values())
                    execute_values(
                        self.cursor, self.sql_queries.set_live_matching, v_to_set
                    )

    @db_exception_handler
    def _update_historic_timetable(
        self, entries_to_update: dict[str, dict[str, Any]], avl_date: str
    ):
        """
        Update Timetable Data
        """
        if len(entries_to_update) > 0:
            for group_id, match_index_dict in entries_to_update.items():
                if len(match_index_dict) > 0:
                    v_to_set = match_index_dict.values()
                    v_to_set_with_date = [(*v, "".join(avl_date)) for v in v_to_set]
                    execute_values(
                        self.cursor,
                        self.sql_queries.set_historic_matching,
                        v_to_set_with_date,
                    )
                    # Update otp state again as the otp calculation is not taking the updated time difference value
                    execute_values(
                        self.cursor,
                        self.sql_queries.update_otp_state,
                        v_to_set_with_date,
                    )

    @db_exception_handler
    def _remove_live_timetable_entries(self, entries_to_remove: list[tuple[str]]):
        """
        Remove or reset specified entries from the Timetable.
        """
        if len(entries_to_remove) > 0:
            execute_values(
                self.cursor,
                self.sql_queries.remove_live_matching,
                entries_to_remove,
            )

    @db_exception_handler
    def _remove_historic_timetable_entries(
        self, entries_to_remove: list[tuple[str]], avl_date: str
    ):
        """
        Remove or reset specified entries from the Timetable for historic matching.
        """
        entries_to_remove_with_date = [
            (*entry, "".join(avl_date)) for entry in entries_to_remove
        ]
        execute_values(
            self.cursor,
            self.sql_queries.remove_historic_matching,
            entries_to_remove_with_date,
        )

    @db_exception_handler
    def _update_batch_status(self, batch_id: str, status: Literal["Success", "Failed"]):
        """
        Update the OTP update status for a specific batch
        """
        self.cursor.execute(
            "UPDATE public.batch SET otp_update_status = %s WHERE batch_id = %s;",
            [status, batch_id],
        )

    def batch_failed(self, batch_id: str):
        self._update_batch_status(batch_id, "Failed")

    @timer(logger)
    def live_update_succcess(
        self,
        batch_id: str,
        entries_to_update: dict[str, dict[str, Any]],
        entries_to_remove: list[tuple[str]],
    ):
        self._remove_live_timetable_entries(entries_to_remove)
        self._update_live_timetable(entries_to_update)
        self._update_batch_status(batch_id, "Success")

    @timer(logger)
    def historic_update_success(
        self,
        batch_id: str,
        entries_to_update: dict[str, dict[str, Any]],
        entries_to_remove: list[tuple[str]],
        avl_date_str: str,
    ):
        self._remove_historic_timetable_entries(entries_to_remove, avl_date_str)
        self._update_historic_timetable(entries_to_update, avl_date_str)
        self._update_batch_status(batch_id, "Success")
