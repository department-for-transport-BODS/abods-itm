import json
import sys
import pprint

import boto3
import psycopg2

shards: dict[str, dict[str, int]] = {
    "0": {},
    "1": {},
    "2": {},
    "3": {},
    "4": {},
    "5": {},
    "6": {},
}


def get_shard_sizes():
    for shard, data in shards.items():
        yield shard, sum(data.values()), len(data.keys())


def potential_shards():
    lowest_stop_count_shard = ("temp", sys.maxsize)
    lowest_operator_count_shard = ("temp", sys.maxsize)
    for shard, stop_count, operator_count in get_shard_sizes():
        if stop_count < lowest_stop_count_shard[1]:
            lowest_stop_count_shard = shard, stop_count
        if operator_count < lowest_operator_count_shard[1]:
            lowest_operator_count_shard = shard, operator_count
    return lowest_stop_count_shard[0], lowest_operator_count_shard[0]


def pick_shard(stop_count):
    fewest_stops, fewest_operators = potential_shards()
    if stop_count == 0:
        return fewest_operators
    return fewest_stops


def process_input():
    client = boto3.client("secretsmanager")
    db_password = json.loads(
        client.get_secret_value(SecretId="abods/uat/rds/user/abods_proxy_rw")[
            "SecretString"
        ]
    )["password"]
    with (
        psycopg2.connect(
            host="localhost",
            port=15432,
            database="abods",
            user="abods_proxy_rw",
            password=db_password,
        ) as connection,
        connection.cursor() as cursor,
    ):
        print("Getting data")
        cursor.execute(
            """
               SELECT o.operatorref,
                      sum(s.completed) AS stop_count
               FROM abods.public.all_operators o
               LEFT OUTER JOIN timetable_summary_operator_t s ON s.operator_noc = o.operatorref
               WHERE s.date_of_journey >= (NOW()::DATE - 14)
               GROUP BY o.operatorref
               ORDER BY stop_count desc;
               """
        )
        inputs = cursor.fetchall()

    for operator_ref, stop_count in inputs:
        shards[pick_shard(stop_count)][operator_ref] = stop_count

    pprint.pp({shard: list(sorted(data.keys())) for shard, data in shards.items()})
    for shard, stop_count, operator_count in get_shard_sizes():
        print(f"shard {shard} has {stop_count} stops and {operator_count} operators")


if __name__ == "__main__":
    process_input()
