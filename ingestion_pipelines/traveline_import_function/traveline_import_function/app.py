import petl
from aws_lambda_powertools import Logger
from psycopg2.extras import execute_values

from .shared.db import setup_db

TRAVELINE_NOC_URL = "https://www.travelinedata.org.uk/wp-content/themes/desktop/qeight_download.php?allGroupsD=-1&allRegionD=-1&allModeD=-1&allCessationD=-1&searchTextD=&maxPage=231&selectPageId=1&downloadType=CSV&submit=Download"

logger = Logger()
conn = setup_db()


def lambda_handler(_event: dict, _context: dict) -> None:
    logger.info("Retrieving data from Traveline")

    noc_table = petl.fromcsv(TRAVELINE_NOC_URL).distinct("NOCCODE")

    logger.info("Converting data to tuples")

    rows = tuple(
        (row["NOCCODE"], row["OperatorPublicName"], row["Licence"], row["Mode"])
        for row in noc_table.dicts()
    )

    with conn.cursor() as cur:
        logger.info("Attempting to create table if not exists")

        cur.execute(
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

        logger.info("Inserting NOC data")

        execute_values(
            cur,
            """
            INSERT INTO traveline_operators (
                noc_code,
                name,
                licence,
                mode
            )
            VALUES %s
            ON CONFLICT (noc_code)
                DO UPDATE SET name = EXCLUDED.name
            """,
            rows,
        )
