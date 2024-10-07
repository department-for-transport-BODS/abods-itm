import psycopg2
from os import environ
import boto3
import logging
from datetime import datetime

s3 = boto3.client("s3")

session = boto3.Session()
db_host = environ.get("POSTGRES_HOST")
db_port = environ.get("POSTGRES_PORT")
db_user = environ.get("POSTGRES_USER")
db_database = environ.get("POSTGRES_DB")
sirivm_bucket = environ.get("SIRIVM_BUCKET")

logger = logging.getLogger("sirivm")
logging.getLogger().setLevel("INFO")


def get_rds_token():
    client = session.client("rds")
    try:
        region = "eu-west-2"
        token = client.generate_db_auth_token(
            DBHostname=db_host, Port=db_port, Region=region, DBUsername=db_user
        )
    except Exception as e:
        logging.error("could not get token ")
        raise e

    return token


def setupDB():
    try:
        logging.info(f"conection creation start ")
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            database=db_database,
            user=db_user,
            password=get_rds_token(),
            sslmode="require",
        )
        conn.autocommit = True
        logging.info(f"conection creation complete ")
    except Exception as e:
        logging.error("DB Connection failed")

    return conn


conn = setupDB()


def lambda_handler(event, context):
    try:
        bucket = sirivm_bucket
        start_time = str(datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"))
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

        for rec in event["Records"]:
            key = rec["messageAttributes"]["key"]["stringValue"]
            batch_id = rec["messageAttributes"]["batch_id"]["stringValue"]
            cur.execute(
                "Update public.batch set db_ingestion_status = 'Inprogress',db_ingestion_strt_prc_ts=%s where batch_id=%s ;",
                [start_time, batch_id],
            )

            try:
                logging.info(f"Truncate the data for batch {batch_id} in staging table")
                cur.execute(
                    f"delete from public.staging_avl_positions where batch_id = {batch_id} ;"
                )
                logging.info(f"Truncate table complete ")
                table_name = "public.staging_avl_positions"
                sql_query = f""" SELECT aws_s3.table_import_from_s3(
                '{table_name}', 'recorded_at_time,response_timestamp,latitude,longitude,line_name,operator_ref,vehicle_ref,journey_ref,direction_ref,date_of_journey,batch_id', '(FORMAT csv, HEADER false, DELIMITER ",")',
                '{bucket}', '{key}', 'eu-west-2'
                );"""
                cur.execute(sql_query)
                logging.info(f"Data Loaded to staging table")
                cur.execute(f"select public.load_avl_tables({batch_id})")
                logging.info(
                    f"Data from staging tables to other tables positions,operators, linenames and journeys populated "
                )
                end_time = str(datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"))
                cur.execute(
                    "Update public.batch set db_ingestion_status = 'Success',db_ingestion_end_prc_ts=%s,s3_avl_gz_key=%s where batch_id=%s ;",
                    [end_time, key, batch_id],
                )
                cur.close()

            except Exception as e:
                end_time = str(datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"))
                cur.execute(
                    "Update public.batch set db_ingestion_status = 'Failed',db_ingestion_end_prc_ts=%s,s3_avl_gz_key=%s where batch_id=%s ;",
                    [end_time, key, batch_id],
                )
                logger.error("Database connection failed due to {}".format(e))
                cur.close()

    except Exception as e:
        logging.error(f"Error connecting to abods DB. Error {e}")
