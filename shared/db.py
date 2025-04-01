from os import environ

import boto3
import psycopg2
from aws_lambda_powertools import Logger

db_host = environ.get("POSTGRES_HOST")
db_port = environ.get("POSTGRES_PORT")
db_user = environ.get("POSTGRES_USER")
db_database = environ.get("POSTGRES_DB")
region = environ.get("AWS_REGION", "eu-west-2")

session = boto3.Session()
client = session.client("rds")

logger = Logger(child=True)


def get_rds_token() -> str:
    try:
        token = client.generate_db_auth_token(
            DBHostname=db_host,
            Port=db_port,
            Region=region,
            DBUsername=db_user,
        )
    except Exception as e:
        logger.exception("Error retrieving RDS token")
        raise RuntimeError("Failed to generate RDS token") from e

    return token


def setup_db() -> psycopg2.extensions.connection:
    try:
        logger.info("Creating new DB connection")
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            database=db_database,
            user=db_user,
            password=get_rds_token(),
            sslmode="require",
        )
        conn.autocommit = True
    except Exception as e:
        logger.exception("Failed to establish DB connection")
        raise RuntimeError("Database connection failed") from e

    return conn
