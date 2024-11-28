import json
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from os import environ

import awswrangler as wr
import boto3
import psycopg2
from dateutil.parser import parse

session = boto3.Session()
db_host = environ.get("POSTGRES_HOST")
db_port = environ.get("POSTGRES_PORT")
db_user = environ.get("POSTGRES_USER")
db_database = environ.get("POSTGRES_DB")
sirivm_bucket = environ.get("SIRIVM_BUCKET")
otp_queue = environ.get("SIRIVM_OTP_QUEUE")
logger = logging.getLogger("sirivm")
logging.getLogger().setLevel("INFO")

client = boto3.client("s3")

no_of_shards = 7

sqs = boto3.resource("sqs")


def get_rds_token():  # noqa: ANN201 - BODS-7131
    client = session.client("rds")
    try:
        region = "eu-west-2"
        token = client.generate_db_auth_token(
            DBHostname=db_host,
            Port=db_port,
            Region=region,
            DBUsername=db_user,
        )
    except Exception as e:
        logging.exception("could not get token ")
        raise e  # noqa: TRY201 - BODS-7131

    return token


def write_to_s3(data_dict, path):  # noqa: ANN001, ANN201 - BODS-7131
    data_string = json.dumps(data_dict, default=str)

    client.put_object(Bucket=sirivm_bucket, Key=path, Body=data_string)


def getQueue(queue):  # noqa: ANN001, ANN201, N802 - BODS-7131
    """Retrieve the URL for the configured queue name"""
    q = sqs.get_queue_by_name(QueueName=queue)
    return q


def read_historic_timetable(timetable_date):  # noqa: ANN001, ANN201 - BODS-7131
    """
    Read historic timetable in csv format

    Args:
        timetable_date (str): The date of the timetable in format YYYY-MM-DD

    Returns:
        list : The list of all rows in the timetable of a input date

    """
    timetable_filename = f"historic_timetable/{timetable_date}.csv"
    colnames = [
        "group_id",
        "stop_index",
        "stop_latitude",
        "stop_longitude",
        "expected_departure_time",
        "timetable_id",
        "date_of_journey",
    ]
    try:
        df = wr.s3.read_csv(  # noqa: PD901 - BODS-7131
            path=f"s3://{sirivm_bucket}/{timetable_filename}",
            names=colnames,
            usecols=colnames,
            header=None,
        )
        timetable = df.to_dict("records")
        logger.info(f"Retrieved timetable {timetable_filename}")
    except Exception as e:  # noqa: BLE001 - BODS-7131
        logger.error(e)  # noqa: TRY400 - BODS-7131
    return timetable


def recreate_timetable(timetable):  # noqa: ANN001, ANN201 - BODS-7131
    """
    Recreate timetable in dict format

    Args:
        timetable (list): list of rows from the input timetable

    Returns:
        dict: Timetable data grouped by group_id

    """
    recreated_timetable = {}
    logger.info("Recreating timetable")
    count = 0
    for row in timetable:
        count += 1  # noqa: SIM113 - BODS-7131
        group_id = row["group_id"]
        if group_id not in recreated_timetable:
            recreated_timetable[group_id] = {}
        recreated_timetable[group_id][str(row["stop_index"])] = [
            [row["stop_latitude"], row["stop_longitude"]],
            row["expected_departure_time"],
            row["timetable_id"],
            row["date_of_journey"],
        ]
        if count % 500000 == 0:
            logger.info(f"reading {count} rows")
    logger.info(f"Recreated timetable with {len(recreated_timetable)} group ids")
    return recreated_timetable


def shred_timetable(recreated_timetable, query_time, timetable_date):  # noqa: ANN001, ANN201 - BODS-7131
    """
    Shred timetable into files in every half an hour interval with a 2-hour sliding window

    Args:
        recreated_timetable (dict): The recreated timetable output from recreate_timetable function
        query_time (datetime): The time interval
        timetable_date (str): The timetable date

    Returns:
        list: A list of rows that are within the 2-hour sliding window

    """
    window_hours = 2
    sliding_window_minus = query_time - timedelta(hours=window_hours)
    sliding_window_plus = query_time + timedelta(hours=window_hours)
    selected_rows = {}
    logger.info(f"Shredding timetable at {query_time}")
    try:
        for group_id, items in recreated_timetable.items():
            for stop, details in items.items():  # noqa: B007, PERF102 - BODS-7131
                journey_time = datetime.strptime(  # noqa: DTZ007 - BODS-7131
                    f"{timetable_date} {details[1]}",
                    "%Y-%m-%d %H:%M:%S",
                )
                if (  # noqa: SIM102 - BODS-7131
                    journey_time > sliding_window_minus
                    and journey_time < sliding_window_plus
                ):
                    if group_id not in selected_rows:
                        selected_rows[group_id] = items
                        # logging.info(f"Adding {group_id} into selected rows")  # noqa: ERA001 - BODS-7131
    except Exception as e:  # noqa: BLE001 - BODS-7131
        logger.error(e)  # noqa: TRY400 - BODS-7131
    return selected_rows


def lambda_handler(event, context):  # noqa: ANN001, ANN201 - BODS-7131
    if event.get("backfill_start_date") and event.get("backfill_end_date"):
        backfill_lambda_handler(event, context)
    else:
        live_lambda_handler(event, context)


def backfill_lambda_handler(event, context):  # noqa: ANN001, ANN201, ARG001, PLR0915 - BODS-7131
    """Receive an event, get backfill start date and end date and start from time and shred the historic timetable into files in every half an hour interval with a 2-hour sliding window"""
    timetable_start_date = event.get("backfill_start_date")
    timetable_end_date = event.get("backfill_end_date")
    start_from_time = event.get("start_from_time")
    if start_from_time:
        start_hour = int(start_from_time[0])
        start_minute = 0 if start_from_time[1] == "00" else 1
    else:
        start_hour = 0
        start_minute = 0
    delta = timedelta(days=1)
    start_date_split = timetable_start_date.split("-")
    end_date_split = timetable_end_date.split("-")
    timetable_start_datetime = datetime.strptime(timetable_start_date, "%Y-%m-%d")  # noqa: DTZ007 - BODS-7131
    timetable_end_datetime = datetime.strptime(timetable_end_date, "%Y-%m-%d")  # noqa: DTZ007 - BODS-7131
    if len(start_date_split) == 3 and len(end_date_split) == 3:  # noqa: PLR2004 - BODS-7131
        while timetable_end_datetime >= timetable_start_datetime:
            timetable_end_date = datetime.strftime(timetable_end_datetime, "%Y-%m-%d")
            end_datetime = parse(timetable_end_date)
            h_year = end_datetime.year
            h_mon = str(end_datetime.month).zfill(2)
            h_day = str(end_datetime.day).zfill(2)
            try:
                historic_timetable = read_historic_timetable(timetable_end_date)
                recreated_timetable = recreate_timetable(historic_timetable)
                shredded_dir = f"timetable_shreds/YYYY={h_year}/MM={h_mon}/DD={h_day}/"
                if "Contents" in client.list_objects(
                    Bucket=sirivm_bucket,
                    Prefix=shredded_dir,
                ):
                    shredded_timetables_list = [
                        obj["Key"]
                        for obj in client.list_objects_v2(
                            Bucket=sirivm_bucket,
                            Prefix=shredded_dir,
                            Delimiter="/",
                        )["Contents"]
                        if obj["Key"][-1] != "/"
                    ]
                    shredded_timetables_list.sort(
                        key=lambda x: int(x[-10:-8] + x[-7:-5]),
                    )
                    number_of_shredded_timetables = len(shredded_timetables_list)
                    if number_of_shredded_timetables < 48:  # noqa: PLR2004 - BODS-7131
                        start_hour = int(shredded_timetables_list[-1][-10:-8])
                        start_minute = (
                            0 if shredded_timetables_list[-1][-7:-5] == "00" else 1
                        )
                logger.info(
                    f"Starting shredding on {h_year}-{h_mon}-{h_day} at {start_hour}:{'00' if start_minute == 0 else '30'}",
                )
                for h in range(start_hour, 24):
                    for i in range(start_minute, 2):
                        if i == 0:  # noqa: SIM108 - BODS-7131
                            minute_str = "00"
                        else:
                            minute_str = "30"
                        hour_str = str(h).zfill(2)
                        query_time = datetime.strptime(  # noqa: DTZ007 - BODS-7131
                            f"{timetable_end_date} {hour_str}{minute_str}",
                            "%Y-%m-%d %H%M",
                        )
                        file_name = (
                            shredded_dir
                            + f"timetable_{h_year}{h_mon}{h_day}_{hour_str}_{minute_str}.json"
                        )
                        timetable_output = shred_timetable(
                            recreated_timetable,
                            query_time,
                            timetable_end_date,
                        )
                        write_to_s3(timetable_output, file_name)
                        logger.info(f"Written {file_name} to s3")
                    start_minute = 0
                start_hour = 0
            except Exception as e:  # noqa: BLE001 - BODS-7131
                logger.error(e)  # noqa: TRY400 - BODS-7131
            timetable_end_datetime -= delta
    else:
        logger.error(
            f"Input backfill date ({timetable_start_date}, {timetable_end_date}) is/are not in a valid format YYYY-MM-DD.",
        )


def live_lambda_handler(event, context):  # noqa: ANN001, ANN201, ARG001 - BODS-7131
    query = """  with my_groups as (
        select distinct vehiclejourney_id
        from public."Timetable" where date_of_journey  = (now() at time zone 'Europe/London')::date
        and expected_departure_time between
        current_timestamp(0) - interval '120' minute and
        current_timestamp(0) +  interval '120' minute
    )
    select t.group_id,row_number() over( partition by t.group_id order by t.group_id,t.expected_departure_time asc,t.stop_index  asc  ) as stop_index , 
    t.stop_latitude,t.stop_longitude,t.expected_departure_time::time as expected_departure_time,t.timetable_id, t.date_of_journey, t.direction
    from public."Timetable" t
    where t.date_of_journey  = now()::date
    and t.vehiclejourney_id in (select vehiclejourney_id from my_groups)
    order by t.group_id,t.expected_departure_time asc,t.stop_index  asc; """  # noqa: W291 - BODS-7131
    now = datetime.now()
    year = datetime.strftime(now, "%Y")
    mon = datetime.strftime(now, "%m")
    day = datetime.strftime(now, "%d")
    hour = datetime.strftime(now, "%H")
    minute = datetime.strftime(now, "%M")
    minute_standardised = "30" if int(minute) >= 30 else "00"  # noqa: PLR2004 - BODS-7131
    fname = f"timetable_shreds/YYYY={year}/MM={mon}/DD={day}/timetable_{year}{mon}{day}_{hour}_{minute_standardised}.json"

    try:
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            database=db_database,
            user=db_user,
            password=get_rds_token(),
            sslmode="require",
        )
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(query)
        timetable_dict = defaultdict(dict)
        res = cur.fetchall()
        directions = set([i[7] for i in res])
        for i in res:
            group_id = i[0]
            if directions.size > 1:
                direction = i[7]
                group_id = group_id + "_" + direction
            timetable_dict[group_id][i[1]] = [(float(i[2]), float(i[3])), i[4], i[5], i[6]]
        cur.close()
        write_to_s3(timetable_dict, "timetable/timetable.json")
        write_to_s3(timetable_dict, fname)
        for shard_no in range(no_of_shards):
            queue_name = f"{otp_queue}{shard_no+1}.fifo"
            queue = getQueue(queue_name)
            resp = queue.send_message(  # noqa: F841 - BODS-7131
                MessageBody="Put gzip file to S3",
                MessageDeduplicationId=str(uuid.uuid4()),
                MessageGroupId=f"{queue_name.split('.')[0]}-group",
                MessageAttributes={
                    "key": {"StringValue": "timetable", "DataType": "String"},
                },
            )
            logging.info(
                f"Send message to  {otp_queue}{shard_no+1} so timetable is refreshed.",
            )
    except Exception as e:
        logging.exception(e)  # noqa: TRY401 - BODS-7131
