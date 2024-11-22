import csv
import gzip
import json
import logging
import time
import urllib.parse
import uuid
import zipfile
from datetime import datetime, timedelta
from io import BytesIO
from os import environ

import boto3
import psycopg2
from aws_lambda_powertools.utilities.data_classes import SQSEvent
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError
from dateutil.parser import parse

from .transform_load_shared_conn import parse_xml

s3 = boto3.client("s3")

session = boto3.Session()
db_host = environ.get("POSTGRES_HOST")
db_port = environ.get("POSTGRES_PORT")
db_user = environ.get("POSTGRES_USER")
db_database = environ.get("POSTGRES_DB")
sirivm_process_bucket = environ.get("SIRIVM_BUCKET")
process_queue = environ.get("SIRIVM_PROCESS_QUEUE")
otp_queue = environ.get("SIRIVM_OTP_QUEUE")
output_csv_file = "/tmp/avl.csv"  # noqa: S108 - BODS-7131
output_gzip_file = "/tmp/avl.gzip"  # noqa: S108 - BODS-7131
logging.getLogger().setLevel("INFO")
sqs = boto3.resource("sqs")
no_of_shards = 7
queues = []

# Upload JSON String to an S3 Object
client = boto3.client("s3")


def getQueue(queue):  # noqa: ANN001, ANN201, N802 - BODS-7131
    """Retrieve the URL for the configured queue name"""
    q = sqs.get_queue_by_name(QueueName=queue)
    return q


def setup_queues(lambda_group):  # noqa: ANN001, ANN201 - BODS-7131
    global queues  # noqa: PLW0603 - BODS-7131
    queues = []
    for shard_no in range(no_of_shards):
        queue_name = f"{otp_queue}-backfill-{lambda_group}-{shard_no+1}.fifo"
        queues.append(getQueue(queue_name))


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


def write_list_to_file(output_csv_file, lst, sirivm_process_bucket, fname):  # noqa: ANN001, ANN201 - BODS-7131
    with open(output_csv_file, "w") as f:
        writer = csv.writer(f)
        writer.writerows(lst)
        with open(output_csv_file, "rb") as f:  # noqa: PLW2901 - BODS-7131
            file_content = f.read()
        with gzip.open(output_gzip_file, "wb") as f:  # noqa: PLW2901 - BODS-7131
            f.write(file_content)
        s3.upload_file(
            output_gzip_file,
            sirivm_process_bucket,
            fname,
            ExtraArgs={"ContentEncoding": "gzip"},
        )
        logging.info(f"gzip file {fname} uploaded to {sirivm_process_bucket} created")


def write_to_s3(data_dict, path):  # noqa: ANN001, ANN201 - BODS-7131
    data_string = json.dumps(data_dict, default=str)

    client.put_object(Bucket=sirivm_process_bucket, Key=path, Body=data_string)


def read_historic_matching_records(run_date):  # noqa: ANN001, ANN201 - BODS-7131
    try:
        progress_file = (
            client.get_object(
                Bucket=sirivm_process_bucket,
                Key=f"timetable_avl/{run_date}/progress.json",
            )
            .get("Body")
            .read()
        )
        progress = json.loads(progress_file)
    except ClientError as ex:
        if ex.response["Error"]["Code"] == "NoSuchKey":
            logging.info("No object found - so returning empty")
            progress = {"control_info": {"last_avl": ""}}
        else:
            raise
    return progress


def lambda_handler(event: dict[str, any], context: LambdaContext) -> None:
    logging.info(
        f"Starting s3 ingestion - Time to Run [{round(context.get_remaining_time_in_millis() / 1000)}] seconds / Memory [{context.memory_limit_in_mb}] Mb",
    )

    if event.get("backfill_start_date") and event.get("backfill_end_date"):
        backfill_lambda_handler(event, context)
    else:
        live_lambda_handler(SQSEvent(event))


def backfill_lambda_handler(event, context):  # noqa: ANN001, ANN201, PLR0915 - BODS-7131
    backfill_start_date = event.get("backfill_start_date")
    backfill_end_date = event.get("backfill_end_date")
    concurrency = int(event.get("concurrency", 10))
    try:
        backfill_start_datetime = datetime.strptime(backfill_start_date, "%Y-%m-%d")  # noqa: DTZ007 - BODS-7131
        backfill_end_datetime = datetime.strptime(backfill_end_date, "%Y-%m-%d")  # noqa: DTZ007 - BODS-7131
        delta = timedelta(days=1)
        lambda_group = concurrency
        setup_queues(lambda_group)
        while backfill_end_datetime >= backfill_start_datetime:
            year = str(backfill_end_datetime.year)
            month = str(backfill_end_datetime.month).zfill(2)
            day = str(backfill_end_datetime.day).zfill(2)
            start_hour = 0
            # if lambda_group > concurrency:
            #     lambda_group = 1  # noqa: ERA001 - BODS-7131
            progress = read_historic_matching_records(f"{year}-{month}-{day}")
            if progress["control_info"]["last_avl"] != "":
                last_avl = progress["control_info"]["last_avl"]
                last_avl_datetime = parse(last_avl)
                start_hour = int(last_avl_datetime.hour)
                logging.info(
                    f"Last avl processed: {last_avl}, Continue historic matching progress from hour: {start_hour}",
                )
            else:
                last_avl = 0
            avl_count = 0
            time_remaining = 0
            for h in range(start_hour, 24):
                start_time_hourly = time.time()
                try:
                    hour = str(h).zfill(2)
                    avl_path = (
                        f"AVL/Processed/YYYY={year}/MM={month}/DD={day}/HH={hour}/"
                    )
                    avl_file_list = [
                        obj["Key"][obj["Key"].rindex("/") + 1 :]
                        for obj in s3.list_objects_v2(
                            Bucket=sirivm_process_bucket,
                            Prefix=avl_path,
                            Delimiter="/",
                        )["Contents"]
                    ]
                    avl_file_list.sort(key=lambda x: int(x[4:-3]))
                    for avl in avl_file_list:
                        if int(avl[4:-3]) >= int(last_avl):
                            fname = avl_path + avl
                            for shard_no in range(len(queues)):
                                queue_name = f"{otp_queue}-backfill-{lambda_group}-{shard_no+1}.fifo"
                                resp = queues[shard_no].send_message(  # noqa: F841 - BODS-7131
                                    MessageBody="AVL to process",
                                    MessageDeduplicationId=str(uuid.uuid4()),
                                    MessageGroupId=f"{queue_name.split('.')[0]}-group",
                                    MessageAttributes={
                                        "bucket": {
                                            "StringValue": sirivm_process_bucket,
                                            "DataType": "String",
                                        },
                                        "key": {
                                            "StringValue": fname,
                                            "DataType": "String",
                                        },
                                        "shard": {
                                            "StringValue": str(shard_no),
                                            "DataType": "String",
                                        },
                                        "Historic": {
                                            "StringValue": "True",
                                            "DataType": "String",
                                        },
                                    },
                                )
                                logging.debug(
                                    f"Written to historic {fname} gzip file key to Queues",
                                )
                            progress["control_info"]["last_avl"] = avl[4:-3]
                            avl_count += 1
                            time_remaining = context.get_remaining_time_in_millis()
                            if time_remaining < 5000:  # noqa: PLR2004 - BODS-7131
                                logging.warning(
                                    f"s3 ingestion processing due to timeout [ts={time_remaining}], last processed hour: {hour}, last processed avl: {avl}",
                                )
                                write_to_s3(
                                    progress,
                                    f"timetable_avl/{year}-{month}-{day}/progress.json",
                                )
                        else:
                            logging.warning(
                                f"avl is not in order/has been processed, avl: {avl}, last avl: {last_avl}",
                            )
                        last_avl = progress["control_info"]["last_avl"]
                    logging.info(
                        f"{year}-{month}-{day}: Last processed hour: {hour}, last processed avl: {progress['control_info']['last_avl']}, avl processed: {avl_count}, Time used: {time.time() - start_time_hourly}s, Time remaining: {time_remaining}ms",
                    )
                except Exception as e:
                    logging.exception(f"Error {e}")  # noqa: TRY401 - BODS-7131
            backfill_end_datetime -= delta
            start_hour = 0
            # lambda_group += 1  # noqa: ERA001 - BODS-7131
    except Exception as e:
        logging.exception(
            f"Input backfill date ({backfill_start_date}, {backfill_end_date}) is/are not in a valid format YYYY-MM-DD. Error {e}",  # noqa: TRY401 - BODS-7131
        )


def live_lambda_handler(event: SQSEvent) -> None:  # noqa: PLR0915 - BODS-7131
    try:
        now = datetime.now()
        year = datetime.strftime(now, "%Y")
        mon = datetime.strftime(now, "%m")
        day = datetime.strftime(now, "%d")
        hour = datetime.strftime(now, "%H")
        created_time = datetime.strftime(now, "%Y%m%d%H%M%S")
        fname = f"AVL/Processed/YYYY={year}/MM={mon}/DD={day}/HH={hour}/avl_{created_time}.gz"
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
        sqlquery = "INSERT INTO public.batch (batch_dt, s3_ingestion_strt_prc_ts ,process_cd,s3_avl_gip_key,s3_ingestion_status) VALUES(%s,%s,%s,%s,%s) RETURNING batch_id;"
        batch_start_time = datetime.now()
        start_time = str(batch_start_time.strftime("%Y-%m-%d %H:%M:%S.%f"))
        batch_dt = str(batch_start_time.strftime("%Y-%m-%d"))
        cur.execute(
            sqlquery,
            [batch_dt, start_time, "sirivm_ingestion", "", "Inprogress"],
        )
        batch_id = cur.fetchone()[0]
        try:
            for rec in event.records:
                sns_event = rec.decoded_nested_sns_event
                message = json.loads(sns_event.message)

                bucket = message["bucket"]
                key = urllib.parse.unquote_plus(
                    message["key"],
                    encoding="utf-8",
                )
                version_id = message["versionId"]
                logging.info(
                    f"Processing AVL bucket {bucket}, file {key}, versionId {version_id}",
                )
                try:
                    obj = s3.get_object(Bucket=bucket, Key=key, VersionId=version_id)
                    zip_file = zipfile.ZipFile(BytesIO(obj["Body"].read()))
                    logging.info(f"Parsed Zip file Successfully {key}")
                    try:
                        logging.info("Parsing XML file")
                        avl_response = parse_xml(
                            zip_file.read(zip_file.namelist()[0]),
                            batch_id,
                            source_type="string",
                        )
                        write_list_to_file(
                            output_csv_file,
                            avl_response,
                            sirivm_process_bucket,
                            fname,
                        )
                        logging.info(
                            f"Writing gzip file to S3 bucket {sirivm_process_bucket}",
                        )
                        queue = getQueue(process_queue)
                        queue.send_message(
                            MessageBody="Put gzip file to S3",
                            MessageAttributes={
                                "bucket": {
                                    "StringValue": sirivm_process_bucket,
                                    "DataType": "String",
                                },
                                "key": {"StringValue": fname, "DataType": "String"},
                                "batch_id": {
                                    "StringValue": str(batch_id),
                                    "DataType": "String",
                                },
                            },
                        )
                        logging.info(
                            f"Written to gzip file key to Queue {process_queue}",
                        )
                        end_time = str(datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"))
                        cur.execute(
                            "Update public.batch set s3_ingestion_status = 'Success',s3_ingestion_end_prc_ts=%s,s3_avl_gip_key=%s where batch_id=%s  ;",
                            [end_time, key, batch_id],
                        )
                        cur.close()
                        # get 7 queues to trigger 7 otp matching lambdas
                        for shard_no in range(no_of_shards):
                            queue_name = f"{otp_queue}{shard_no+1}.fifo"
                            queue = getQueue(queue_name)
                            queue.send_message(  # noqa: F841 - BODS-7131
                                MessageBody="Put gzip file to S3",
                                MessageDeduplicationId=str(uuid.uuid4()),
                                MessageGroupId=f"{queue_name.split('.')[0]}-group",
                                MessageAttributes={
                                    "bucket": {
                                        "StringValue": sirivm_process_bucket,
                                        "DataType": "String",
                                    },
                                    "key": {"StringValue": fname, "DataType": "String"},
                                    "batch_id": {
                                        "StringValue": str(batch_id),
                                        "DataType": "String",
                                    },
                                    "shard": {
                                        "StringValue": str(shard_no),
                                        "DataType": "String",
                                    },
                                },
                            )
                            logging.info(
                                f"Written to gzip file key to Queues {queue_name}",
                            )
                    except Exception as e:
                        end_time = str(datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"))
                        logging.exception(
                            f"Lambda failed either connecting to database or processing AVL Zip file or writing to queue. Error {e}",  # noqa: TRY401 - BODS-7131
                        )
                        cur.execute(
                            "Update public.batch set s3_ingestion_status = 'Failed',s3_ingestion_end_prc_ts=%s,s3_avl_gip_key=%s where batch_id=%s ;",
                            [end_time, key, batch_id],
                        )
                        cur.close()
                        # raise e
                except Exception as e:
                    end_time = str(datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"))
                    logging.exception(
                        f"Error getting object {key} from bucket {bucket}. Error {e}",  # noqa: TRY401 - BODS-7131
                    )
                    cur.execute(
                        "Update public.batch set s3_ingestion_status = 'Failed',s3_ingestion_end_prc_ts=%s,s3_avl_gip_key=%s  where batch_id=%s ;",
                        [end_time, key, batch_id],
                    )
                    cur.close()
                    # raise e
        except Exception as e:
            end_time = str(datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"))
            logging.info(f"Event {event}")
            logging.exception(f"Error consuming the event. Error {e}")  # noqa: TRY401 - BODS-7131
            cur.execute(
                "Update public.batch set s3_ingestion_status = 'Failed',s3_ingestion_end_prc_ts=%s where batch_id=%s ;",
                [end_time, batch_id],
            )
            cur.close()
            # raise e
    except Exception as e:
        logging.exception(f"Error connecting to abods DB. Error {e}")  # noqa: TRY401 - BODS-7131
