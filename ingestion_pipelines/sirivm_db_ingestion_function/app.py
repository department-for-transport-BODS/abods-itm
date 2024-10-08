from datetime import datetime
from os import environ
from typing import Any

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.data_classes import SQSEvent
from aws_lambda_powertools.utilities.typing import LambdaContext
from psycopg2.extensions import cursor

from .shared.db import setup_db

sirivm_bucket = environ["SIRIVM_BUCKET"]
region = environ.get("AWS_REGION", "eu-west-2")

logger = Logger()
conn = setup_db()


def update_batch_status(
    cur: cursor,
    batch_id: str,
    status: str,
    start_time: str,
    end_time: str | None,
    key: str,
) -> None:
    cur.execute(
        """
        UPDATE public.batch SET
            db_ingestion_status = %s,
            db_ingestion_strt_prc_ts = %s,
            db_ingestion_end_prc_ts = %s,
            s3_avl_gz_key = %s
        WHERE batch_id = %s;
        """,
        [status, start_time, end_time, key, batch_id],
    )


def process_batch(
    cur: cursor,
    bucket: str,
    key: str,
    batch_id: str,
) -> None:
    logger.info(f"Processing batch {batch_id}")

    # Delete staging table
    cur.execute(
        "DELETE FROM public.staging_avl_positions WHERE batch_id = %s;",
        [batch_id],
    )
    logger.info("Staging table truncated")

    # Import data from S3
    table_name = "public.staging_avl_positions"
    cur.execute(
        """
        SELECT aws_s3.table_import_from_s3(
            %s,
            'recorded_at_time,response_timestamp,latitude,longitude,line_name,operator_ref,vehicle_ref,journey_ref,direction_ref,date_of_journey,batch_id',
            '(FORMAT csv, HEADER false, DELIMITER ",")',
            %s,
            %s,
            %s
        );
        """,
        [table_name, bucket, key, region],
    )
    logger.info("Data loaded to staging table")

    # Load AVL tables
    cur.execute("SELECT public.load_avl_tables(%s)", [batch_id])
    logger.info(
        "Data from staging tables populated to positions, operators, linenames, and journeys tables",
    )


def lambda_handler(event: dict[str, Any], _: LambdaContext) -> None:
    sqs_event = SQSEvent(event)
    bucket = sirivm_bucket
    start_time = datetime.now().isoformat()

    with conn.cursor() as cur:
        for record in sqs_event.records:
            key = record.message_attributes["key"].string_value
            batch_id = record.message_attributes["batch_id"].string_value

            logger.append_keys(batch_id=batch_id, key=key)

            try:
                update_batch_status(cur, batch_id, "Inprogress", start_time, None, key)
                process_batch(cur, bucket, key, batch_id)
                final_status = "Success"
                logger.info("Batch processed successfully")
            except Exception:
                final_status = "Failed"
                logger.exception("Error processing batch")
                raise
            finally:
                end_time = datetime.now().isoformat()
                update_batch_status(
                    cur,
                    batch_id,
                    final_status,
                    start_time,
                    end_time,
                    key,
                )
                logger.info("Batch status updated")
