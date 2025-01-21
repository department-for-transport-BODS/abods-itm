import csv
import json
import os
from pathlib import Path
from unittest import mock

import boto3
import psycopg2

from ..live_timetable_store import LiveTimetableStore
from ..matching import match_group_id_avls
from .util import parse_live_avl_data

directory = Path(__file__).parent


def create_connection() -> psycopg2.extensions.connection:
    try:
        return psycopg2.connect(
            host="localhost",
            port=15432,
            database="abods",
            user="abods_proxy_rw",
            password=(
                json.loads(
                    boto3.client("secretsmanager").get_secret_value(
                        SecretId="abods/sandbox/rds/user/abods_proxy_rw",
                    )["SecretString"],
                )["password"]
            ),
            sslmode="require",
        )
    except Exception as e:
        raise Exception(  # noqa:TRY002
            "Ensure sure that you are serving a connection to the sandbox db on localhost",
        ) from e


def get_db_data(
    connection: psycopg2.extensions.connection,
    group_id: str,
    avl_destination: Path,
    timetable_destination: Path,
) -> None:
    # We used to use different group id formats, so match the constituent parts for now
    group_id_parts = group_id.split("|")
    with connection.cursor() as cursor:
        cursor.execute(
            """
                SELECT to_char((recorded_at_time AT TIME ZONE 'UTC')::timestamp, 'YYYY-MM-DD"T"HH24:MI:SS.MSOF') as recorded_at_time,
                       to_char((response_time_stamp AT TIME ZONE 'UTC')::timestamp, 'YYYY-MM-DD"T"HH24:MI:SS.MSOF') as response_timestamp,
                       latitude,
                       longitude,
                       line_name,
                       operator_ref,
                       vehicle_ref,
                       journey_ref,
                       direction_ref,
                       date_of_journey,
                       batch_id
                FROM "SiriVMPositions"
                WHERE date_of_journey = %s
                  AND operator_ref = %s
                  AND journey_ref = %s
                  AND LOWER(line_name) = %s
                ORDER BY recorded_at_time
            """,
            [
                group_id_parts[3],
                group_id_parts[0].upper(),
                group_id_parts[2],
                group_id_parts[1],
            ],
        )
        rows = cursor.fetchall()

    with open(avl_destination, "w") as csv_file:
        avl_file = csv.writer(csv_file, lineterminator="\n")
        avl_file.writerow(
            [
                "recorded_at_time",
                "response_timestamp",
                "latitude",
                "longitude",
                "line_name",
                "operator_ref",
                "vehicle_ref",
                "journey_ref",
                "direction_ref",
                "date_of_journey",
                "batch_id",
            ],
        )
        avl_file.writerows(rows)

        with connection.cursor() as cursor:
            cursor.execute(
                """
                    SELECT row_number() OVER (PARTITION BY vehiclejourney_id
                                              ORDER BY group_id, expected_departure_time ASC, stop_index ASC) AS stop_index,
                           stop_latitude,
                           stop_longitude,
                           ((expected_departure_time AT TIME ZONE 'UTC')::TIME)::TEXT AS expected_departure_time,
                           timetable_id,
                           date_of_journey::TEXT,
                           direction
                    FROM public."Timetable"
                    WHERE date_of_journey = %s
                      AND operator_noc = %s
                      AND journey_code = %s
                      AND LOWER(line_name) = %s
                    ORDER BY stop_index
                """,
                [
                    group_id_parts[3],
                    group_id_parts[0].upper(),
                    group_id_parts[2],
                    group_id_parts[1],
                ],
            )
            rows = cursor.fetchall()
    directions = set()
    for i in rows:
        directions.add(i[6])
    timetable = {}
    for i in rows:
        timetable_index = group_id
        if len(directions) > 1:
            direction = i[6]
            timetable_index = group_id + "|" + direction
        timetable.setdefault(timetable_index, {})[str(i[0])] = [
            (float(i[1]), float(i[2])),
            i[3],
            i[4],
            i[5],
        ]
    with open(timetable_destination, "w") as json_file:
        json.dump(timetable, json_file)


def main() -> None:
    group_id = input("What is the example's group_id? ")
    example_dir_name = group_id.replace("|", "_").replace("-", "_")
    example_dir = directory / example_dir_name
    if not example_dir.is_dir():
        example_dir.mkdir()

    avl_destination = example_dir / "avl.csv"
    timetable_destination = example_dir / "timetable.json"

    with create_connection() as connection:
        get_db_data(connection, group_id, avl_destination, timetable_destination)

    with open(avl_destination) as csvfile:
        avl_list = parse_live_avl_data(csvfile)
    with open(timetable_destination) as jsonfile:
        timetable = json.load(jsonfile)

    with mock.patch.dict(os.environ, {"ENABLE_ESTIMATED_MATCHING": "true"}):
        to_set, _, __ = match_group_id_avls(LiveTimetableStore(timetable), avl_list)

    with open(example_dir / "__init__.py", "w"):
        pass
    with open(example_dir / "test_matching.py", "w") as test_file:
        test_file.write(f'''# TODO: Add description of what makes the journey unique
""""""
import datetime

from ..util import run_historic_matching_test

matches = {to_set}


def test_historic_match() -> None:
    assert run_historic_matching_test(__file__) == matches
''')


if __name__ == "__main__":
    main()
