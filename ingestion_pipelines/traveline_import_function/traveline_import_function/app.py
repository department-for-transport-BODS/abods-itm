import logging
from os import environ

import boto3
import petl
import psycopg2

db_host = environ.get("POSTGRES_HOST")
db_port = environ.get("POSTGRES_PORT")
db_user = environ.get("POSTGRES_USER")
db_database = environ.get("POSTGRES_DB")

logger = logging.getLogger("sirivm")
logging.getLogger().setLevel("INFO")


def get_rds_token():  # noqa: ANN201 - BODS-7131
    session = boto3.Session()
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
        logging.exception("could not get token", e)  # noqa: PLE1205, TRY401 - BODS-7131
        raise e  # noqa: TRY201 - BODS-7131

    return token


def lambda_handler(event, context):  # noqa: ANN001, ANN201, ARG001 - BODS-7131
    try:
        url = "https://www.travelinedata.org.uk/wp-content/themes/desktop/qeight_download.php?allGroupsD=-1&allRegionD=-1&allModeD=-1&allCessationD=-1&searchTextD=&maxPage=231&selectPageId=1&downloadType=CSV&submit=Download"
        logging.info(f"Getting data from url {url}")
        noc_table = petl.fromcsv(url).distinct("NOCCODE")

        logging.info("Converting data to tuples")
        rows = tuple(
            (row["NOCCODE"], row["OperatorPublicName"], row["Licence"], row["Mode"])
            for row in noc_table.dicts()
        )

        logging.info(f"Connecting to db {db_host}")
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            database=db_database,
            user=db_user,
            password=get_rds_token(),
            sslmode="require",
        )
        with conn.cursor() as cursor:
            logging.info("Attempting to create table if not exists")
            cursor.execute(
                """
                    CREATE TABLE IF NOT EXISTS traveline_operators (
                        noc_code varchar NOT NULL,
                        "name" varchar NULL,
                        licence varchar NULL,
                        "mode" varchar NULL,
                        CONSTRAINT travelinedata_pk PRIMARY KEY (noc_code)
                    );
                """,
            )
            logging.info("Mogrifying input data")
            args_str = ",".join(
                cursor.mogrify("(%s,%s, %s, %s)", x).decode("utf-8") for x in rows
            )

            logging.info("Inserting input data")
            cursor.execute(
                f"""
                    INSERT INTO traveline_operators (
                        noc_code,
                        name,
                        licence,
                        mode
                    )
                    VALUES {args_str}
                    ON CONFLICT (noc_code)
                    do update set name = EXCLUDED.name""",  # noqa: S608 - BODS-7131
            )

            logging.info("Committing data")
            conn.commit()
    except Exception as e:  # noqa: BLE001 - BODS-7131
        print("Couldn't write to database: ", e)  # noqa: T201 - BODS-7131
