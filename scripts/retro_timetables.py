import subprocess
import time
from datetime import datetime, timedelta
from getpass import getpass
import sys
import select

db_host = "abods-prod-db.cluster-cpwu8ksu6zyo.eu-west-2.rds.amazonaws.com"
db_user = "root"


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
    # TODO: get from secrets manager
    db_password = getpass(f"Enter password for database user {db_user}: ")
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
        time.sleep(
            10 * 60
        )  # Give live matching time to catch up after DOSing it by hogging the Timetable table
        # TODO: Convert the timetable data and start historic matching

        print(f"{datetime.now()} Generated {dstr} timetable")

        if select.select([sys.stdin], [], [], 0.0)[0]:
            for line in sys.stdin:
                if "q" == line.rstrip():
                    sys.exit(0)
                break
        current = current - timedelta(days=1)


if __name__ == "__main__":
    main()
