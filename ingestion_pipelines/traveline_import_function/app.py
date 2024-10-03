import psycopg2
from os import environ
import petl
import boto3
import logging

db_host = environ.get('POSTGRES_HOST')
db_port = environ.get('POSTGRES_PORT')
db_user = environ.get('POSTGRES_USER')
db_database = environ.get('POSTGRES_DB')

logger = logging.getLogger('sirivm')
logging.getLogger().setLevel('INFO')

def get_rds_token():
    session = boto3.Session()
    client = session.client('rds')
    try:
        region="eu-west-2"
        token = client.generate_db_auth_token(DBHostname=db_host, Port=db_port, Region=region, DBUsername=db_user)
    except Exception as e:
        logging.error("could not get token", e)
        raise e
        
    return token

def lambda_handler(event, context):
    try:
        url = 'https://www.travelinedata.org.uk/wp-content/themes/desktop/qeight_download.php?allGroupsD=-1&allRegionD=-1&allModeD=-1&allCessationD=-1&searchTextD=&maxPage=231&selectPageId=1&downloadType=CSV&submit=Download'
        logging.info(f"Getting data from url {url}")
        noc_table = petl.fromcsv(url).distinct('NOCCODE')

        logging.info(f"Converting data to tuples")
        rows = tuple((row['NOCCODE'], row['OperatorPublicName'],row['Licence'], row['Mode']) for row in noc_table.dicts())

        logging.info(f"Connecting to db {db_host}")
        conn = psycopg2.connect(host=db_host, port=db_port, database=db_database, user=db_user, password=get_rds_token(), sslmode='require')
        with conn.cursor() as cursor:
            logging.info(f"Attempting to create table if not exists")
            cursor.execute(
                f'''
                    CREATE TABLE IF NOT EXISTS traveline_operators (
                        noc_code varchar NOT NULL,
                        "name" varchar NULL,
                        licence varchar NULL,
                        "mode" varchar NULL,
                        CONSTRAINT travelinedata_pk PRIMARY KEY (noc_code)
                    );
                '''
            )
            logging.info(f"Mogrifying input data")
            args_str = ','.join(cursor.mogrify("(%s,%s, %s, %s)", x).decode("utf-8") for x in rows)

            logging.info(f"Inserting input data")
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
                    do update set name = EXCLUDED.name"""
            )

            logging.info(f"Committing data")
            conn.commit()
    except Exception as e:
        print("Couldn't write to database: ", e)