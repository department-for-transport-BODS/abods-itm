import json
import subprocess
import time
from datetime import datetime, timedelta
import sys
import select

import boto3

db_host = "abods-prod-db.cluster-cpwu8ksu6zyo.eu-west-2.rds.amazonaws.com"
db_user = "root"
max_queue_length = 6


def get_db_password():
    return json.loads(
        boto3.client("secretsmanager").get_secret_value(
            SecretId=f"abods/prod/rds/user/{db_user}",
        )["SecretString"],
    )["password"]


def wait_for_queues():
    while True:
        longest_queue = 0
        sqs = boto3.client("sqs")
        for shard in range(7, 0, -1):
            queue_length = int(
                sqs.get_queue_attributes(
                    QueueUrl=f"https://sqs.eu-west-2.amazonaws.com/637423206165/abods-prod-sirivm-otp-queue{7}.fifo",
                    AttributeNames=["ApproximateNumberOfMessages"],
                )["Attributes"]["ApproximateNumberOfMessages"]
            )
            if queue_length > longest_queue:
                longest_queue = queue_length

            if queue_length > max_queue_length:
                print(
                    f"{datetime.now().isoformat()}: Queue {shard} has {queue_length} messages"
                )
                break
        else:
            print(
                f"{datetime.now().isoformat()}: All queues have {longest_queue} messages or less"
            )
            return

        time.sleep(60)


def run_query(query: str, password: str):
    subprocess.run(
        [
            # This is where it's installed on the bastion, doesn't seem to be on PATH when called by subprocess
            "/usr/bin/psql",
            "--echo-queries",
            "--dbname=abods",
            "-h",
            db_host,
            "-U",
            db_user,
            "-c",
            query,
        ],
        env={"PGPASSWORD": password},
        check=True,
    )


def main():
    db_password = get_db_password()
    while True:
        try:
            start = datetime.fromisoformat(
                input("Enter start date in yyyy-mm-dd format: ")
            )
            break
        except ValueError:
            print("Incorrect data format, should be YYYY-MM-DD")
    while True:
        try:
            current = datetime.fromisoformat(
                input("Enter end date in yyyy-mm-dd format: ")
            )
            break
        except ValueError:
            print("Incorrect data format, should be YYYY-MM-DD")
    while current >= start:
        dstr = current.strftime("%Y-%m-%d")
        print(f"{datetime.now()} Generating {dstr} timetable")
        print("hit q then enter to exit after completion")
        run_query(
            f"CALL public.generate_retrospective_timetable('{dstr}');",
            password=db_password,
        )
        run_query(
            f"CALL public.historic_timetable_export('{dstr}');", password=db_password
        )
        wait_for_queues()

        print(f"{datetime.now()} Generated {dstr} timetable")

        if select.select([sys.stdin], [], [], 0.0)[0]:
            for line in sys.stdin:
                if "q" == line.rstrip():
                    sys.exit(0)
                break
        current = current - timedelta(days=1)


if __name__ == "__main__":
    main()
