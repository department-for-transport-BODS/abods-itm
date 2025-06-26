from collections.abc import Sequence
from datetime import date, timedelta
from typing import Literal

import psycopg2.extras
from aws_lambda_powertools import Logger
from psycopg2.extras import execute_values

from .matcher.models import BadDbMatch, NewDbMatch
from .matcher.utils import timer
from .shared.db import setup_db

logger = Logger()


def _update_batch_status(
    cursor: psycopg2.extensions.cursor,
    batch_id: int | None,
    status: Literal["Success", "Failed"],
) -> None:
    """Update the OTP update status for a specific batch"""
    logger.debug("Setting OTP update status")
    cursor.execute(
        "UPDATE public.batch SET otp_update_status = %s WHERE batch_id = %s;",
        [status, batch_id],
    )


def chunked(iterable, chunk_size):
    """Yield successive chunks from iterable."""
    for i in range(0, len(iterable), chunk_size):
        yield iterable[i : i + chunk_size]


def execute_values_amended(
    cur: psycopg2.extensions.cursor,
    sql: str,
    values: list,
) -> None:
    logger.debug("Executing SQL query", sql=sql, values=values)
    for batch in chunked(values, 2000):
        result = execute_values(
            cur=cur,
            sql=sql,
            argslist=batch,
            fetch=True,
        )
        expected = len(values)
        actual = len(result)
        if expected == actual:
            logger.debug("Updated all rows", expected=expected, actual=actual)
        else:
            result_timetable_id = [r[0] for r in result]
            not_updated = [v for v in values if v[0] not in result_timetable_id]
            logger.warning(
                "An unexpected number of rows were updated",
                not_updated=not_updated,
                expected=expected,
                actual=actual,
            )


class TimetableDBClient:
    def __init__(self) -> None:
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
        entries_to_update: Sequence[NewDbMatch],
        entries_to_remove: Sequence[BadDbMatch],
        process_date: date,
    ) -> None:
        """Update database to reflect successful live matching"""
        with self.connection.cursor() as cursor:
            # In the time after midnight, we may have matched a stop where the date_of_journey is
            # the previous day, so we should hint both values for the partition to the db
            alternate_date = process_date - timedelta(days=1)
            if len(entries_to_remove) > 0:
                execute_values_amended(
                    cur=cursor,
                    sql="""
                        UPDATE public."Timetable" u
                        SET time_difference = NULL,
                            actual_departure_time = NULL,
                            otp_state = NULL,
                            load_time_stamp = now()::timestamp(0),
                            timestamp_after_estimate = NULL
                        FROM (VALUES %s) AS t(timetable_id, journey_date, alternate_journey_date)
                        WHERE u.timetable_id = t.timetable_id::bigint
                          AND date_of_journey IN (t.journey_date::date, t.alternate_journey_date::date)
                        RETURNING u.timetable_id;
                    """,
                    values=[
                        (
                            entry["timetable_id"],
                            process_date.isoformat(),
                            alternate_date.isoformat(),
                        )
                        for entry in entries_to_remove
                    ],
                )

            execute_values_amended(
                cur=cursor,
                sql="""
                    UPDATE public."Timetable" u
                    SET time_difference = t.time_difference::int,
                        actual_departure_time = t.last_time_in_zone_utc::timestamp AT TIME ZONE 'UTC',
                        timestamp_after_estimate = t.timestamp_after_estimate::timestamp AT TIME ZONE 'UTC',
                        -- When passengers aren't being picked up, we don't consider it early
                        otp_state = CASE WHEN (u.set_down IS NOT NULL AND u.set_down AND t.otp_state = 'Early') THEN 'OnTime' ELSE t.otp_state::TEXT END,
                        load_time_stamp = now()::timestamp(0)
                    FROM (VALUES %s) AS t(timetable_id, time_difference, last_time_in_zone_utc, otp_state, timestamp_after_estimate, journey_date, alternate_journey_date)
                    WHERE u.timetable_id = t.timetable_id::bigint
                      AND date_of_journey IN (t.journey_date::date, t.alternate_journey_date::date)
                    RETURNING u.timetable_id;
                """,
                values=[
                    (
                        record["timetable_id"],
                        record["time_difference"],
                        record["last_time_in_zone"],
                        record["otp_state"],
                        record["timestamp_after_estimate"],
                        process_date.isoformat(),
                        alternate_date.isoformat(),
                    )
                    for record in entries_to_update
                ],
            )

            _update_batch_status(cursor, batch_id, "Success")

    @timer(logger)
    def historic_update_success(
        self,
        entries_to_update: Sequence[NewDbMatch],
        process_date: date,
        log_level: str | None = None,
    ) -> None:
        """Update database to reflect successful historic matching"""
        if log_level:
            logger.setLevel(log_level)
        with self.connection.cursor() as cursor:
            # In historic matching, we know that the date we're working with is always the right,
            # but it doesn't hurt to align the code with live matching, so that we can deduplicate later
            alternate_date = process_date - timedelta(days=1)
            values = [
                (
                    record["timetable_id"],
                    record["time_difference"],
                    record["last_time_in_zone"],
                    record["stop_type"],
                    record["timestamp_after_estimate"],
                    process_date.isoformat(),
                    alternate_date.isoformat(),
                )
                for record in entries_to_update
            ]
            execute_values_amended(
                cur=cursor,
                sql="""
                    -- Recalculating time difference when it's less than zero to make sure it's calculated correctly
                    UPDATE public."Timetable" u
                    SET time_difference          =
                            CASE
                                WHEN t.time_difference::int < 0 THEN
                                    COALESCE(
                                            EXTRACT(epoch FROM(t.last_time_in_zone_utc::timestamp AT TIME ZONE 'UTC' - u.expected_departure_time)),
                                            EXTRACT(epoch FROM (t.timestamp_after_estimate::timestamp AT TIME ZONE 'UTC' - u.expected_departure_time))
                                    )::int
                                ELSE t.time_difference::int
                            END,
                        actual_departure_time    = t.last_time_in_zone_utc::timestamp AT TIME ZONE 'UTC',
                        timestamp_after_estimate = t.timestamp_after_estimate::timestamp AT TIME ZONE 'UTC',
                        load_time_stamp          = now()::timestamp(0)
                    FROM (VALUES %s) AS t(timetable_id, time_difference, last_time_in_zone_utc, is_final_stop, timestamp_after_estimate, journey_date, alternate_journey_date)
                    WHERE u.timetable_id = t.timetable_id::bigint
                      AND date_of_journey IN (t.journey_date::date, t.alternate_journey_date::date)
                    RETURNING u.timetable_id;
                """,
                values=values,
            )
            # Update otp state again as the otp calculation is not taking the updated time difference value
            execute_values_amended(
                cur=cursor,
                sql="""
                    UPDATE public."Timetable" u
                    SET otp_state = CASE
                                        WHEN u.time_difference::int > 359 THEN 'Late'
                                        -- If it's the final stop, we don't consider it early
                                        WHEN (t.is_final_stop = 'Non-final'
                                          -- When passengers aren't being picked up, we don't consider it early
                                          AND (u.set_down IS NULL OR NOT u.set_down)
                                          AND u.time_difference::int < -60) THEN 'Early'
                                        ELSE 'OnTime'
                                    END,
                        load_time_stamp = now()::timestamp(0)
                    FROM (VALUES %s) AS t(timetable_id, time_difference, last_time_in_zone_utc, is_final_stop, timestamp_after_estimate, journey_date, alternate_journey_date)
                    WHERE u.timetable_id = t.timetable_id::bigint
                      AND date_of_journey IN (t.journey_date::date, t.alternate_journey_date::date)
                      AND COALESCE (
                                  EXTRACT(epoch FROM (t.last_time_in_zone_utc::timestamp AT TIME ZONE 'UTC' - u.expected_departure_time)),
                                  EXTRACT(epoch FROM (t.timestamp_after_estimate::timestamp AT TIME ZONE 'UTC' - u.expected_departure_time)),
                                  0
                          ) > -7200
                    RETURNING u.timetable_id;
                """,
                values=values,
            )
