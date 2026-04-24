import csv
import gzip
import json
import logging
import urllib.parse
import uuid
from datetime import datetime
from os import environ

import boto3
import psycopg2
from aws_lambda_powertools.utilities.data_classes import SQSEvent
from aws_lambda_powertools.utilities.typing import LambdaContext

from .transform_load_shared_conn import parse_xml

s3 = boto3.client("s3")

session = boto3.Session()
db_host = environ.get("POSTGRES_HOST")
db_port = environ.get("POSTGRES_PORT")
db_user = environ.get("POSTGRES_USER")
db_database = environ.get("POSTGRES_DB")
sirivm_process_bucket = environ.get("SIRIVM_BUCKET")
process_queue = environ.get("SIRIVM_PROCESS_QUEUE")
otp_queue = environ.get("SIRIVM_OTP_QUEUE_PREFIX")
output_csv_file = "/tmp/avl.csv"  # noqa: S108 - BODS-7131
output_gzip_file = "/tmp/avl.gzip"  # noqa: S108 - BODS-7131
logging.getLogger().setLevel("INFO")
sqs = boto3.resource("sqs")
no_of_shards = 7
queues = []

# Upload JSON String to an S3 Object
client = boto3.client("s3")


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
        logging.exception("could not get token ")  # noqa: LOG015
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
        logging.info(f"gzip file {fname} uploaded to {sirivm_process_bucket} created")  # noqa: LOG015


def update_s3_ingestion_status(  # noqa: ANN201 
        cur,
        batch_id,
        status,
        end_time,
        key,
):
        cur.execute(
                """
                UPDATE public.batch
                SET s3_ingestion_status = %s,
                        s3_ingestion_end_prc_ts = %s,
                        s3_avl_gip_key = COALESCE(%s, s3_avl_gip_key)
                WHERE batch_id = %s
                    AND (
                        s3_ingestion_status IS DISTINCT FROM %s
                        OR s3_ingestion_end_prc_ts IS DISTINCT FROM %s
                        OR (%s IS NOT NULL AND s3_avl_gip_key IS DISTINCT FROM %s)
                    );
                        """,
                    [status, end_time, key, batch_id, status, end_time, key, key],
        )


def lambda_handler(event: dict[str, any], context: LambdaContext) -> None:  # noqa: PLR0915 - BODS-7131
    logging.info(  # noqa: LOG015
        f"Starting s3 ingestion - Time to Run [{round(context.get_remaining_time_in_millis() / 1000)}] seconds / Memory [{context.memory_limit_in_mb}] Mb",
    )

    event = SQSEvent(event)
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
                logging.info(  # noqa: LOG015
                    f"Processing AVL bucket {bucket}, file {key}, versionId {version_id}",
                )
                try:
                    obj = s3.get_object(Bucket=bucket, Key=key, VersionId=version_id)
                    try:
                        logging.info("Parsing XML file")  # noqa: LOG015
                        avl_response = parse_xml(
                            obj["Body"].read(),
                            batch_id,
                            source_type="string",
                        )
                        write_list_to_file(
                            output_csv_file,
                            avl_response,
                            sirivm_process_bucket,
                            fname,
                        )
                        logging.info(  # noqa: LOG015
                            f"Writing gzip file to S3 bucket {sirivm_process_bucket}",
                        )
                        queue = sqs.get_queue_by_name(QueueName=process_queue)
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
                        logging.info(  # noqa: LOG015
                            f"Written to gzip file key to Queue {process_queue}",
                        )
                        end_time = str(datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"))
                        update_s3_ingestion_status(
                            cur,
                            batch_id,
                            "Success",
                            end_time,
                            key,
                        )
                        cur.close()
                        # get 7 queues to trigger 7 otp matching lambdas
                        for shard_no in range(no_of_shards):
                            queue_name = f"{otp_queue}{shard_no + 1}.fifo"
                            try:
                                queue = sqs.get_queue_by_name(QueueName=queue_name)
                                queue.send_message(  # noqa: F841 - BODS-7131
                                    MessageBody="Put gzip file to S3",
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
                            except Exception:
                                logging.exception(  # noqa: LOG015
                                    "Failed to write message to queue",
                                    extra={"queue_name": queue_name},
                                )
                                raise
                            logging.info(  # noqa: LOG015
                                f"Written to gzip file key to Queues {queue_name}",
                            )
                    except Exception as e:
                        end_time = str(datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"))
                        logging.exception(  # noqa: LOG015
                            f"Lambda failed either connecting to database or processing AVL Zip file or writing to queue. Error {e}",  # noqa: TRY401 - BODS-7131
                        )
                        update_s3_ingestion_status(
                            cur,
                            batch_id,
                            "Failed",
                            end_time,
                            key,
                        )
                        cur.close()
                        # raise e
                except Exception as e:
                    end_time = str(datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"))
                    logging.exception(  # noqa: LOG015
                        f"Error getting object {key} from bucket {bucket}. Error {e}",  # noqa: TRY401 - BODS-7131
                    )
                    update_s3_ingestion_status(
                        cur,
                        batch_id,
                        "Failed",
                        end_time,
                        key,
                    )
                    cur.close()
                    # raise e
        except Exception as e:
            end_time = str(datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"))
            logging.info(f"Event {event}")  # noqa: LOG015
            logging.exception(f"Error consuming the event. Error {e}")  # noqa: LOG015, TRY401
            update_s3_ingestion_status(
                cur,
                batch_id,
                "Failed",
                end_time,
                None,
            )
            cur.close()
            # raise e
    except Exception as e:
        logging.exception(f"Error connecting to abods DB. Error {e}")  # noqa: LOG015, TRY401
