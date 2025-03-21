#!/usr/bin/env python3
import json
import subprocess
from datetime import datetime, date, timedelta
from subprocess import CalledProcessError
from time import sleep
from zoneinfo import ZoneInfo

import boto3
from botocore.config import Config

db_host = "abods-prod-db.cluster-cpwu8ksu6zyo.eu-west-2.rds.amazonaws.com"
db_user = "root"
s3 = boto3.client("s3")
paginator = s3.get_paginator("list_objects_v2")
base_prefix = "historic/"
max_queue_length = 6


def list_files(environment: str, prefix: str):
    bucket = f"abods-{environment}-exporter-bucket"
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for item in page["Contents"]:
            yield item["Key"]


def parse_task_output(output: dict):
    for task in output["tasks"]:
        containers = [
            container
            for container in task["containers"]
            if container["name"] == "matcher"
        ]
        if len(containers) != 1:
            continue
        status: str = containers[0]["lastStatus"]
        arn: str = containers[0]["taskArn"]
        process_date = date.fromisoformat(
            [
                var["value"]
                for var in task["overrides"]["containerOverrides"][0]["environment"]
                if var["name"] == "PROCESS_DATE"
            ][0]
        )
        yield arn, status, process_date


def run_matching(process_date: date, environment: str):
    ssm = boto3.client("ssm")
    private_subnet_ids = ssm.get_parameter(
        Name=f"/abods/{environment}/vpc/subnets/private",
    )["Parameter"]["Value"].split(",")
    vpc_sg_ids = ssm.get_parameter(
        Name=f"/abods/{environment}/ec2/securitygroup/rdsproxy-access/id",
    )["Parameter"]["Value"].split(",")

    ecs = boto3.client("ecs")
    return ecs.run_task(
        cluster=f"abods-{environment}",
        taskDefinition=f"abods-{environment}-historic-matching",
        count=1,
        networkConfiguration={
            "awsvpcConfiguration": {
                "subnets": private_subnet_ids,
                "securityGroups": vpc_sg_ids,
            }
        },
        overrides={
            "containerOverrides": [
                {
                    "name": "matcher",
                    "environment": [
                        {"name": "PROCESS_DATE", "value": process_date.isoformat()},
                        {
                            "name": "SIRIVM_BUCKET",
                            "value": f"abods-{environment}-exporter-bucket",
                        },
                    ],
                }
            ]
        },
    )


def get_task_status(environment: str, task_arns: list[str]):
    return boto3.client("ecs").describe_tasks(
        cluster=f"abods-{environment}", tasks=task_arns
    )


running_tasks = {}


def start_historic_matching(current: date, environment: str):
    run_output = run_matching(current, environment)
    for task_arn, status, process_date in parse_task_output(run_output):
        running_tasks[task_arn] = {
            "status": status,
            "process_date": process_date,
        }
        cloudwatch = cloudwatch_logs_link(task_arn, environment)
        print(
            f"{datetime.now().isoformat()}: {process_date} started. You can read the logs at {cloudwatch}"
        )


def look_for_existing_tasks(environment: str):
    arns = boto3.client("ecs").list_tasks(cluster=f"abods-{environment}")["taskArns"]
    if not arns:
        return
    status_output = get_task_status(environment, arns)
    for task_arn, status, process_date in parse_task_output(status_output):
        print(
            f"{datetime.now().isoformat()}: {task_arn} for date {process_date.isoformat()} is {status}"
        )
        running_tasks[task_arn] = {
            "status": status,
            "process_date": process_date,
        }


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

        sleep(60)


def run_query(query: str, db_password: str):
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
        env={"PGPASSWORD": db_password},
        check=True,
    )


def timetable_generation(db_password: str, process_date: date):
    run_query(
        f"CALL generate_timetable('{process_date.isoformat()}');",
        db_password,
    )
    wait_for_queues()


def timetable_export(db_password: str, process_date: date):
    run_query(
        f"CALL historic_timetable_export('{process_date.isoformat()}');",
        db_password,
    )


def avl_export(db_password: str, process_date: date):
    run_query(
        f"CALL historic_avl_export('{process_date.isoformat()}');",
        db_password,
    )


def convert_to_parquet(process_date: date, environment: str):
    print("Converting avl and timetable csv data to parquet format")
    response = boto3.client(
        "lambda",
        config=Config(
            read_timeout=15 * 60,
        ),
    ).invoke(
        FunctionName=f"abods-{environment}-convert-to-parquet-function",
        Payload=json.dumps(
            {
                "process_date": process_date.isoformat(),
                "skip_timetable": "false",
                "skip_avl": "false",
                "overwrite_existing_output": "true",
            }
        ),
    )
    print(f"Lambda returned {response['StatusCode']}")
    print(json.loads(response["Payload"].read()))


def summary_generation(db_password: str, process_date: date):
    run_query(
        f"CALL historic_matching_summary_generation('{process_date.isoformat()}');",
        db_password,
    )


def cloudwatch_logs_link(arn: str, environment: str):
    return f"https://eu-west-2.console.aws.amazon.com/cloudwatch/home?region=eu-west-2#logsV2:log-groups/log-group/$252Faws$252Fecs$252Fabods-{environment}/log-events/historic-matching$252Fmatcher$252F{arn.split('/')[-1]}"


def check_for_completed_tasks(environment: str):
    if not running_tasks:
        return []
    status_output = get_task_status(environment, list(running_tasks))
    found_arns = []
    for task_arn, status, process_date in parse_task_output(status_output):
        found_arns.append(task_arn)
        if running_tasks[task_arn]["status"] != status:
            print(
                f"{datetime.now().isoformat()}: {task_arn} for date {process_date.isoformat()} is {status}"
            )
        running_tasks[task_arn]["status"] = status

    completed_dates: list[date] = []
    for arn in list(running_tasks):
        status = running_tasks[arn]["status"]
        process_date = running_tasks[arn]["process_date"]
        cloudwatch = cloudwatch_logs_link(arn, environment)

        if status in ("STOPPED", "DELETED"):
            completed_dates.append(process_date)
            del running_tasks[arn]
            print(
                f"{datetime.now().isoformat()}: {process_date.isoformat()} finished. You can read the logs at {cloudwatch}"
            )
            continue

        if arn not in found_arns:
            completed_dates.append(process_date)
            del running_tasks[arn]
            print(
                f"{datetime.now().isoformat()}: {process_date.isoformat()} was not found in the list. You can read the logs at {cloudwatch}. Assuming it completed successfully"
            )
            continue
    return completed_dates


def get_db_password(environment: str):
    return json.loads(
        boto3.client("secretsmanager").get_secret_value(
            SecretId=f"abods/{environment}/rds/user/{db_user}",
        )["SecretString"],
    )["password"]


def get_dates_to_run():
    while True:
        try:
            process_dates = input(
                "Enter start date in yyyy-mm-dd format or a list of semicolon separated dates with the same format: "
            )
            process_dates = process_dates.split(";")
            process_dates = {
                date.fromisoformat(date_val)
                for date_val in process_dates
                if date_val != ""
            }
            if process_dates:
                break
            print("You must enter at least one value")
        except ValueError:
            print("Incorrect data format, should be YYYY-MM-DD")
    if len(process_dates) < 2:
        current = min(process_dates)
        while True:
            try:
                end = date.fromisoformat(input("Enter end date in yyyy-mm-dd format: "))
                if end < current:
                    print("End date needs to come after start")
                    continue
                break
            except ValueError:
                print("Incorrect data format, should be YYYY-MM-DD")
        while current < end:
            current = current + timedelta(days=1)
            process_dates.add(current)
    return process_dates


def in_service_hours():
    current_time = datetime.now(ZoneInfo("Europe/London"))

    if current_time.weekday() > 4:
        print("It's the weekend")
        return False

    if current_time.hour < 8:
        print("It's early morning")
        return False

    if current_time.hour > 18:
        print("It's the evening")
        return False

    print("It's working hours, no blocking the database now")
    return True


def main():
    while True:
        environment = input("Which environment? (prod|sandbox): ")
        if environment == "sandbox":
            break
        if environment == "prod":
            break
        print("Wrong, try again")
    process_dates = get_dates_to_run()

    look_for_existing_tasks(environment)
    for arn in list(running_tasks):
        process_date = running_tasks[arn]["process_date"]

        if process_date in process_dates:
            process_dates.remove(process_date)

    if running_tasks:
        print("The following dates currently have an executing matching task:")
        print(
            ";".join(
                data["process_date"].isoformat() for arn, data in running_tasks.items()
            )
        )

    files = list(list_files(environment, base_prefix))

    avl_export_needed = []
    timetable_export_needed = []
    ready_to_run = []

    for current in process_dates:
        year = current.year
        month = str(current.month).zfill(2)
        day = str(current.day).zfill(2)
        date_with_dashes = f"{year}-{month}-{day}"
        date_without_dashes = f"{year}{month}{day}"
        year_month_prefix = f"YYYY={year}/MM={month}"
        year_month_day_prefix = f"{year_month_prefix}/DD={day}"
        timetable_csv_path = (
            f"{base_prefix}csv/timetable/{year_month_prefix}/{date_with_dashes}.csv"
        )
        timetable_parquet_path = f"{base_prefix}parquet/{year_month_day_prefix}/timetable_{date_without_dashes}.parquet"
        avl_csv_path = (
            f"{base_prefix}csv/siri/{year_month_prefix}/siri_vm_{date_with_dashes}.csv"
        )
        avl_gz_path = (
            f"{base_prefix}gz/{year_month_day_prefix}/{date_with_dashes}.csv.gz"
        )
        avl_parquet_path = f"{base_prefix}parquet/{year_month_day_prefix}/siri_vm_{date_without_dashes}.parquet"
        data = {
            "timetable_csv": (timetable_csv_path in files),
            "timetable_parquet": (timetable_parquet_path in files),
            "avl_csv": avl_csv_path in files,
            "avl_gz": (avl_gz_path in files),
            "avl_parquet": (avl_parquet_path in files),
        }
        if data["avl_parquet"] and data["timetable_parquet"]:
            ready_to_run.append(current)
            continue
        if not data["avl_csv"]:
            avl_export_needed.append(current)
            continue
        timetable_export_needed.append(current)

    ready_to_run = sorted(ready_to_run)
    avl_export_needed = sorted(avl_export_needed)
    timetable_export_needed = sorted(timetable_export_needed)

    if ready_to_run:
        print("Will run matching for the following dates:")
        print(";".join(d.isoformat() for d in ready_to_run))

    if avl_export_needed:
        print(
            "Will export AVL data for the following dates before exporting timetable data as well:"
        )
        print(";".join(d.isoformat() for d in avl_export_needed))

    if timetable_export_needed:
        print("Will export timetable data for the following dates:")
        print(";".join(d.isoformat() for d in timetable_export_needed))

    regenerate_timetables = False
    if timetable_export_needed or avl_export_needed:
        regenerate_timetables = (
            input("Should timetable data be re-generated before export? (yes/NO)")
            .lower()
            .strip()
            == "yes"
        )
        if regenerate_timetables:
            print("Will regenerate timetables")

    db_password = get_db_password(environment)

    max_tasks = 5
    summaries_to_run = []
    while (
        ready_to_run
        or running_tasks
        or summaries_to_run
        or avl_export_needed
        or timetable_export_needed
    ):
        if ready_to_run and len(running_tasks) < max_tasks:
            start_historic_matching(ready_to_run.pop(0), environment)
            if ready_to_run:
                print(
                    f"{datetime.now().isoformat()}: Dates still queued for matching: {';'.join(d.isoformat() for d in ready_to_run)}"
                )

                # Keep starting tasks if there's more we can run
                continue

        completed_dates = check_for_completed_tasks(environment)
        summaries_to_run = sorted({*summaries_to_run, *completed_dates})
        if completed_dates:
            print(
                f"{datetime.now().isoformat()}: Dates queued for summary generation: {';'.join(d.isoformat() for d in summaries_to_run)}"
            )

            # Need to start more tasks before doing summary generation
            continue

        if summaries_to_run and not in_service_hours():
            process_date = summaries_to_run.pop(0)
            try:
                summary_generation(db_password, process_date)
            except CalledProcessError as e:
                print(e)
                summary_generation(db_password, process_date)
            if summaries_to_run:
                print(
                    f"{datetime.now().isoformat()}: Dates queued for summary generation: {';'.join(d.isoformat() for d in summaries_to_run)}"
                )
            continue

        if avl_export_needed:
            process_date = avl_export_needed.pop(0)
            avl_export(db_password, process_date)
            timetable_export_needed = sorted({*timetable_export_needed, process_date})
        elif timetable_export_needed and not ready_to_run:
            process_date = timetable_export_needed.pop(0)
            if regenerate_timetables:
                timetable_generation(db_password, process_date)
            timetable_export(db_password, process_date)
            convert_to_parquet(process_date, environment)
            ready_to_run = sorted({*ready_to_run, process_date})

        sleep(60)


if __name__ == "__main__":
    main()
