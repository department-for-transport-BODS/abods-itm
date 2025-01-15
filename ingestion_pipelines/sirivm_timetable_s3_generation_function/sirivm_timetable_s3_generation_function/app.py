import json
import logging
import uuid
from collections import defaultdict
from datetime import datetime
from os import environ

import boto3
import psycopg2

from .shared.config import (
    EXPECTED_LATE_RUNNING_SERVICE_INTERVAL_IN_MINUTES,
    TIMETABLE_EXTRACT_SLIDING_WINDOW_TIME_IN_MINUTES,
)

session = boto3.Session()
db_host = environ.get("POSTGRES_HOST")
db_port = environ.get("POSTGRES_PORT")
db_user = environ.get("POSTGRES_USER")
db_database = environ.get("POSTGRES_DB")
sirivm_bucket = environ.get("SIRIVM_BUCKET")
otp_queue = environ.get("SIRIVM_OTP_QUEUE_PREFIX")
logger = logging.getLogger("sirivm")
logging.getLogger().setLevel("INFO")

client = boto3.client("s3")

no_of_shards = 7

sqs = boto3.resource("sqs")


def lambda_handler(event, context):  # noqa: ANN001, ANN201, ARG001 - BODS-7131
    token = session.client("rds").generate_db_auth_token(
        DBHostname=db_host,
        Port=int(db_port),
        Region="eu-west-2",
        DBUsername=db_user,
    )
    with psycopg2.connect(
        host=db_host,
        port=db_port,
        database=db_database,
        user=db_user,
        password=token,
        sslmode="require",
    ) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            interval_time = TIMETABLE_EXTRACT_SLIDING_WINDOW_TIME_IN_MINUTES
            late_running_interval = EXPECTED_LATE_RUNNING_SERVICE_INTERVAL_IN_MINUTES
            now = datetime.now()
            cur.execute(
                """
                WITH partitions AS (
                   SELECT (now() AT TIME ZONE 'EUROPE/LONDON' + interval '%s' MINUTE)::date AS date UNION
                   SELECT (now() AT TIME ZONE 'EUROPE/LONDON')::date AS date UNION
                   SELECT (now() AT TIME ZONE 'EUROPE/LONDON' - interval '%s' MINUTE)::date AS date
                )
                WITH my_groups AS
                  (SELECT DISTINCT vehiclejourney_id
                   FROM public."Timetable"
                   WHERE date_of_journey IN (SELECT DISTINCT date FROM partitions)
                     AND expected_departure_time BETWEEN
                       current_timestamp(0) - interval '%s' MINUTE AND
                       current_timestamp(0) + interval '%s' MINUTE)
                SELECT t.group_id,
                       row_number() OVER (PARTITION BY t.vehiclejourney_id
                                          ORDER BY t.group_id,
                                                   t.expected_departure_time ASC,
                                                   t.stop_index ASC) AS stop_index,
                       t.stop_latitude,
                       t.stop_longitude,
                       t.expected_departure_time::TIME AS expected_departure_time,
                       t.timetable_id,
                       t.date_of_journey,
                       t.direction
                FROM public."Timetable" t
                WHERE t.date_of_journey IN (SELECT DISTINCT date FROM partitions)
                  AND t.vehiclejourney_id IN
                    (SELECT vehiclejourney_id
                     FROM my_groups)
                ORDER BY t.group_id,
                         t.expected_departure_time ASC,
                         t.stop_index ASC;
                """,
                [
                    interval_time,
                    interval_time + late_running_interval,
                    interval_time,
                    interval_time,
                ],
            )
            timetable_dict = defaultdict(dict)
            res = cur.fetchall()
    directions_by_group_id = {}
    for i in res:
        directions_by_group_id.setdefault(i[0], set()).add(i[7])

    for i in res:
        group_id = i[0]
        directions = directions_by_group_id[group_id]
        if len(directions) > 1:
            direction = i[7]
            group_id = group_id + "|" + direction
        timetable_dict[group_id][i[1]] = [
            (float(i[2]), float(i[3])),
            i[4],
            i[5],
            i[6],
        ]

    timetable_json = json.dumps(timetable_dict, default=str)
    client.put_object(
        Bucket=sirivm_bucket,
        Key="timetable/timetable.json",
        Body=timetable_json,
    )
    # Store a separate copy of the extract for matching debugging
    client.put_object(
        Bucket=sirivm_bucket,
        Key=(
            "timetable/"
            "archive/"
            f"YYYY={datetime.strftime(now, '%Y')}/"
            f"MM={datetime.strftime(now, '%m')}/"
            f"DD={datetime.strftime(now, '%d')}/"
            f"timetable_{datetime.strftime(now, '%Y%m%d%H%M%S')}.json"
        ),
        Body=timetable_json,
    )

    for shard_no in range(no_of_shards):
        group = f"{otp_queue}{shard_no + 1}"
        queue_name = f"{group}.fifo"
        try:
            queue = sqs.get_queue_by_name(QueueName=queue_name)
            resp = queue.send_message(  # noqa: F841 - BODS-7131
                MessageBody="Put gzip file to S3",
                MessageDeduplicationId=str(uuid.uuid4()),
                MessageGroupId=f"{group}-group",
                MessageAttributes={
                    "key": {"StringValue": "timetable", "DataType": "String"},
                },
            )
        except Exception:
            logging.exception(f"Failed to write to queue {queue_name}")
            raise
        logging.info(
            f"Send message to  {otp_queue}{shard_no + 1} so timetable is refreshed.",
        )
