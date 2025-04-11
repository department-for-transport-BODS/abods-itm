import csv
import json
from datetime import datetime, timedelta
from pathlib import Path

import boto3
import psycopg2

from ..matching import match_group_id_avls
from ..models import (
    Timetable,
    stop_departure_time,
)
from ..timetable_store import TimetableStore
from .util import parse_test_avl_file

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


def get_avl_data(
    connection: psycopg2.extensions.connection,
    group_id: str,
    min_time: datetime,
    max_time: datetime,
) -> list[tuple]:
    with connection.cursor() as cursor:
        avls = []
        current = min_time.date()
        while current <= max_time.date():
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
                      AND group_id = %s
                      AND recorded_at_time >= (%s::timestamptz - interval '240' minute)
                      AND recorded_at_time <= (%s::timestamptz + interval '240' minute)
                    ORDER BY recorded_at_time, direction_ref, vehicle_ref desc
                """,
                [
                    current.isoformat(),
                    group_id[: group_id.rfind("|")] + "|" + current.isoformat(),
                    min_time.isoformat(),
                    max_time.isoformat(),
                ],
            )
            avls.extend(cursor.fetchall())
            current = current + timedelta(days=1)
        return avls


def write_avl_data(data: list[tuple], destination: Path) -> None:
    with open(destination, "w") as csv_file:
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
        avl_file.writerows(data)


def get_timetable_data(
    connection: psycopg2.extensions.connection,
    group_id: str,
) -> Timetable:
    with connection.cursor() as cursor:
        cursor.execute(
            """
                SELECT row_number() OVER (PARTITION BY vehiclejourney_id
                                          ORDER BY group_id, expected_departure_time ASC, stop_index ASC) AS stop_index,
                       stop_latitude,
                       stop_longitude,
                       ((expected_departure_time AT TIME ZONE 'UTC')::TIME)::TEXT AS expected_departure_time,
                       timetable_id,
                       ((expected_departure_time AT TIME ZONE 'UTC')::DATE)::TEXT AS expected_departure_date,
                       direction
                FROM public."Timetable"
                WHERE date_of_journey = %s
                  AND group_id = %s
                ORDER BY stop_index
            """,
            [group_id[group_id.rfind("|") + 1 :], group_id],
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
            timetable_index = timetable_index + "|" + direction
        timetable.setdefault(timetable_index, {})[str(i[0])] = [
            (float(i[1]), float(i[2])),
            i[3],
            i[4],
            i[5],
        ]
    return timetable


def write_timetable_data(timetable: Timetable, destination: Path) -> None:
    with open(destination, "w") as json_file:
        json.dump(timetable, json_file)


def get_db_data(
    connection: psycopg2.extensions.connection,
    group_id: str,
    avl_destination: Path,
    timetable_destination: Path,
) -> None:
    # We used to use different group id formats, so match the constituent parts for now
    group_id_parts = group_id.split("|")

    timetable = get_timetable_data(connection, group_id)
    write_timetable_data(timetable, timetable_destination)

    departure_times = [
        stop_departure_time(stop)
        for route in timetable.values()
        for stop in route.values()
    ]
    min_time = datetime.fromisoformat(group_id_parts[3])
    max_time = min_time + timedelta(days=1, milliseconds=-1)
    if departure_times:
        min_time = min(departure_times) - timedelta(hours=4)
        max_time = max(departure_times) + timedelta(hours=4)

    avl_data = get_avl_data(connection, group_id, min_time, max_time)
    write_avl_data(avl_data, avl_destination)


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
        avl_list = list(parse_test_avl_file(csvfile))
    with open(timetable_destination) as jsonfile:
        timetable = json.load(jsonfile)

    to_set, _, __ = match_group_id_avls(TimetableStore(timetable), avl_list)

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
