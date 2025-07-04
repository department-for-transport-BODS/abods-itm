#!/usr/bin/env python3
"""Remember to update this script on the instance where it runs"""

import json
import os
import subprocess
from datetime import datetime, date, timedelta
from subprocess import CalledProcessError
from time import sleep
from typing import Optional
from zoneinfo import ZoneInfo

import boto3
from botocore.config import Config

import shutil

import asyncio
import re
import concurrent.futures

DB_USER = "root"
BASE_PREFIX = "historic/"
MAX_LIVE_MATCHING_QUEUE_LENGTH = 6
MAX_CONCURRENT_MATCHING_TASKS = 5

custom_executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)

s3 = boto3.client("s3")
paginator = s3.get_paginator("list_objects_v2")

lambda_client = boto3.client(
        "lambda",
        config=Config(
            read_timeout=15 * 60,
        ),
    )


def get_db_host(environment: str):
    rds_client = boto3.client("rds")
    response = rds_client.describe_db_clusters(
        DBClusterIdentifier=f"abods-{environment}-db"
    )
    return response["DBClusters"][0]["Endpoint"]


def current_time_london():
    return datetime.now(ZoneInfo("Europe/London"))


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
    print(f"start_historic_matching------{current}")
    run_output = run_matching(current, environment)
    for task_arn, status, process_date in parse_task_output(run_output):
        running_tasks[task_arn] = {
            "status": status,
            "process_date": process_date,
        }
        cloudwatch = cloudwatch_logs_link(task_arn, environment)
        print(
            f"{current_time_london().isoformat()}: {process_date} started. You can read the logs at {cloudwatch}"
        )


def look_for_existing_tasks(environment: str):
    arns = boto3.client("ecs").list_tasks(cluster=f"abods-{environment}")["taskArns"]
    if not arns:
        return
    status_output = get_task_status(environment, arns)
    for task_arn, status, process_date in parse_task_output(status_output):
        print(
            f"{current_time_london().isoformat()}: {task_arn} for date {process_date.isoformat()} is {status}"
        )
        running_tasks[task_arn] = {
            "status": status,
            "process_date": process_date,
        }


def get_aws_account_id():
    sts_client = boto3.client("sts")
    response = sts_client.get_caller_identity()
    return response["Account"]


def wait_for_queues(environment: str):
    account_id = get_aws_account_id()
    while True:
        longest_queue = 0
        sqs = boto3.client("sqs")
        for shard in range(7, 0, -1):
            queue_length = int(
                sqs.get_queue_attributes(
                    QueueUrl=f"https://sqs.eu-west-2.amazonaws.com/{account_id}/abods-{environment}-sirivm-otp-queue{7}.fifo",
                    AttributeNames=["ApproximateNumberOfMessages"],
                )["Attributes"]["ApproximateNumberOfMessages"]
            )
            if queue_length > longest_queue:
                longest_queue = queue_length

            if queue_length > MAX_LIVE_MATCHING_QUEUE_LENGTH:
                print(
                    f"{current_time_london().isoformat()}: Queue {shard} has {queue_length} messages"
                )
                break
        else:
            print(
                f"{current_time_london().isoformat()}: All queues have {longest_queue} messages or less"
            )
            return

        sleep(60)


def run_query2(query: str, db_host: str, db_password: str):
    psql_path = shutil.which("psql")
    if not psql_path:
        raise RuntimeError("psql not found in PATH")
    subprocess.run(
        [
            # This is where it's installed on the bastion, doesn't seem to be on PATH when called by subprocess
            psql_path,
            "--echo-queries",
            "--dbname=abods",
            "-h",
            '127.0.0.1',
            "-p",
            '15432',
            "-U",
            DB_USER,
            "-c",
            query,
        ],
        env={"PGPASSWORD": db_password},
        check=True,
    )


def run_query(query: str, db_host: str, db_password: str):
    psql_path = shutil.which("psql")
    if not psql_path:
        raise RuntimeError("psql not found in PATH")
    subprocess.run(
        [
            # This is where it's installed on the bastion, doesn't seem to be on PATH when called by subprocess
            psql_path,
            "--echo-queries",
            "--dbname=abods",
            "-h",
            db_host,
            "-U",
            DB_USER,
            "-c",
            query,
        ],
        env={"PGPASSWORD": db_password},
        check=True,
    )


def timetable_generation(
    db_password: str, db_host: str, process_date: date, environment: str, subset: bool
):
    if subset:
        run_query(
            f"CALL generate_timetable_unregistered_subset('{process_date.isoformat()}');",
            db_host,
            db_password,
        )
    else:
        run_query(
            f"CALL generate_timetable('{process_date.isoformat()}');",
            db_host,
            db_password,
        )
    wait_for_queues(environment)


def timetable_export(db_password: str, db_host: str, process_date: date, subset: bool):
    print('timetable_export called*****')
    if subset:
        run_query(
            f"CALL historic_timetable_export_unregistered_subset('{process_date.isoformat()}');",
            db_host,
            db_password,
        )
    else:
        run_query(
            f"CALL historic_timetable_export('{process_date.isoformat()}');",
            db_host,
            db_password,
        )

def subset_avl_export(db_password: str, db_host: str, process_date: date):
    run_query(
        f"CALL historic_avl_export('{process_date.isoformat()}');",
        db_host,
        db_password,
    )


def timetable_export2(db_password: str, db_host: str, process_date: date, subset: bool, journeys_sql_list: str = None):
    print('timetable_export called*****')
    if subset:
        run_query2(
            f"CALL historic_timetable_export_unregistered_subset('{process_date.isoformat()}');",
            db_host,
            db_password,
        )
    else:
        if journeys_sql_list:
            run_query2(
                f"CALL historic_subset_timetable_export('{process_date.isoformat()}',ARRAY[{journeys_sql_list}]::text[]);",
                db_host,
                db_password,
            )
            return
        run_query2(
            f"CALL historic_timetable_export('{process_date.isoformat()}');",
            db_host,
            db_password,
        )


def avl_export2(db_password: str, db_host: str, process_date: date, journeys_sql_list: str = None):
    if journeys_sql_list:
        run_query2(
            f"CALL historic_subset_avl_export('{process_date.isoformat()}',ARRAY[{journeys_sql_list}]::text[]);",
            db_host,
            db_password,
        )
        return
    run_query2(
        f"CALL historic_avl_export('{process_date.isoformat()}');",
        db_host,
        db_password,
    )


def avl_export(db_password: str, db_host: str, process_date: date, journeys_sql_list: str = None):
    if journeys_sql_list:
        run_query(
            f"CALL historic_subset_avl_export('{process_date.isoformat()}',ARRAY[{journeys_sql_list}]::text[]);",
            db_host,
            db_password,
        )
        return
    run_query(
        f"CALL historic_avl_export('{process_date.isoformat()}');",
        db_host,
        db_password,
    )


def convert_avl_to_parquet(process_date: date, environment: str):
    print("Converting avl csv data to parquet format")
    response = lambda_client.invoke(
        FunctionName=f"abods-{environment}-convert-to-parquet-function",
        Payload=json.dumps(
            {
                "process_date": process_date.isoformat(),
                "skip_timetable": "true",
                "skip_avl": "false",
                "overwrite_existing_output": "true",
            }
        ),
    )
    print(f"Lambda returned {response['StatusCode']}")
    print(json.loads(response["Payload"].read()))

    
def convert_to_parquet(process_date: date, environment: str):
    print("Converting timetable csv data to parquet format")
    response = lambda_client.invoke(
        FunctionName=f"abods-{environment}-convert-to-parquet-function",
        Payload=json.dumps(
            {
                "process_date": process_date.isoformat(),
                "skip_timetable": "false",
                "skip_avl": "true",
                "overwrite_existing_output": "true",
            }
        ),
    )
    print(f"Lambda returned {response['StatusCode']}")
    print(json.loads(response["Payload"].read()))


def summary_generation(
    db_password: str, db_host: str, process_date: date, subset: bool
):
    def run_summary_generation():
        if subset:
            run_query(
                f"CALL unregistered_subset_post_matching_functions('{process_date.isoformat()}');",
                db_host,
                db_password,
            )
        else:
            run_query(
                f"CALL historic_matching_summary_generation('{process_date.isoformat()}');",
                db_host,
                db_password,
            )

    try:
        run_summary_generation()
    except CalledProcessError as e:
        print(e)
        print(
            "Trying once more, because the daily summaries may have interrupted this one"
        )
        run_summary_generation()


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
                f"{current_time_london().isoformat()}: {task_arn} for date {process_date.isoformat()} is {status}"
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
                f"{current_time_london().isoformat()}: {process_date.isoformat()} finished. You can read the logs at {cloudwatch}"
            )
            continue

        if arn not in found_arns:
            completed_dates.append(process_date)
            del running_tasks[arn]
            print(
                f"{current_time_london().isoformat()}: {process_date.isoformat()} was not found in the list. You can read the logs at {cloudwatch}. Assuming it completed successfully"
            )
            continue
    return completed_dates


def get_db_password(environment: str):
    return json.loads(
        boto3.client("secretsmanager").get_secret_value(
            SecretId=f"abods/{environment}/rds/user/{DB_USER}",
        )["SecretString"],
    )["password"]


def get_boolean_input(prompt: str):
    return input(f"{prompt} (y/N): ").lower().strip()[0] == "y"


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
    earliest_possible_date = date.today() - timedelta(days=2)
    for process_date in process_dates:
        if process_date > earliest_possible_date:
            print(
                f"Can't process a date after {earliest_possible_date}, as we don't have the required AVL data yet. (hint: matching for a date can continue past midnight)"
            )
            exit(1)
    return process_dates


def in_service_hours():
    current_time = current_time_london()

    if current_time.weekday() > 4:
        print(f"{current_time.isoformat()}: It's the weekend")
        return False

    if current_time.hour < 8:
        print(f"{current_time.isoformat()}: It's early morning")
        return False

    if current_time.hour > 17:
        print(f"{current_time.isoformat()}: It's the evening")
        return False

    print(
        f"{current_time.isoformat()}: It's working hours, no blocking the database now"
    )
    return True


def which_files_exist(current: date, files: list[str]):
    year = current.year
    month = str(current.month).zfill(2)
    day = str(current.day).zfill(2)
    date_with_dashes = f"{year}-{month}-{day}"
    date_without_dashes = f"{year}{month}{day}"
    year_month_prefix = f"YYYY={year}/MM={month}"
    year_month_day_prefix = f"{year_month_prefix}/DD={day}"
    timetable_csv_path = (
        f"{BASE_PREFIX}csv/timetable/{year_month_prefix}/{date_with_dashes}.csv"
    )
    timetable_parquet_path = f"{BASE_PREFIX}parquet/{year_month_day_prefix}/timetable_{date_without_dashes}.parquet"
    avl_csv_path = (
        f"{BASE_PREFIX}csv/siri/{year_month_prefix}/siri_vm_{date_with_dashes}.csv"
    )
    avl_gz_path = f"{BASE_PREFIX}gz/{year_month_day_prefix}/{date_with_dashes}.csv.gz"
    avl_parquet_path = f"{BASE_PREFIX}parquet/{year_month_day_prefix}/siri_vm_{date_without_dashes}.parquet"
    data = {
        "timetable_csv": (timetable_csv_path in files),
        "timetable_parquet": (timetable_parquet_path in files),
        "avl_csv": avl_csv_path in files,
        "avl_gz": (avl_gz_path in files),
        "avl_parquet": (avl_parquet_path in files),
    }
    return data


def main():
    is_local = False
    while True:
        environment = input("Which environment? (prod|uat|sandbox|local): ").strip().lower()
        if environment == "local":
            is_local = True
            environment = "sandbox"
            break
        if environment == "sandbox":
            break
        if environment == "uat":
            break
        if environment == "prod":
            break
        print("Wrong, try again")

    sirivm_bucket= f'abods-{environment}-exporter-bucket'
    db_host = get_db_host(environment)
    subset = get_boolean_input("Process only unregistered subset?")
    force_timetable_export = False
    if subset:
        print("Will only process unregistered subset")
    else:
        print("Will process whole timetable")
        force_timetable_export = get_boolean_input("Force export of timetable data?")

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
    
    input_journeys = input("Enter journey group ids (comma-separated values of format opref|line|journeycode|journeydate):")
    skip_summary_generation = get_boolean_input("Skip generating summaries?")

    raw_values = [v.strip() for v in input_journeys.lower().split(',') if v.strip()]
    pattern = re.compile(r'^([^|]+\|){3}\d{4}-\d{2}-\d{2}$')
    journeys = [v for v in raw_values if pattern.match(v)]
    sql_quoted_journeys = [f"'{v}'" for v in journeys]
    sql_list_journeys = ", ".join(sql_quoted_journeys)

    files = list(list_files(environment, BASE_PREFIX))

    avl_export_needed = []
    avl_parquet_only = []
    timetable_export_needed = []
    timetable_parquet_only= []
    ready_to_run = []

    def prep_data(current: date, include_timetable_export: bool = False):
        current_data = which_files_exist(current, files)
        if not current_data["avl_csv"] or input_journeys:
            avl_export_needed.append(current)

        if current_data["avl_csv"] and not current_data["avl_parquet"]:
            avl_parquet_only.append(current)

        if include_timetable_export:
            if subset or force_timetable_export:
                timetable_export_needed.append(current)
                return

            if not current_data["timetable_csv"]:
                timetable_export_needed.append(current)

            if current_data["avl_csv"] and not current_data["avl_parquet"]:
                timetable_parquet_only.append(current)


    for current in process_dates:
        prep_data(current, include_timetable_export=True)

        next_day = current + timedelta(days=1)
        if next_day in process_dates:
            continue
        prep_data(next_day)


    async def csv_to_parquet(avl_parquet: list[date], timetable_parquet: list[date]):
        loop = asyncio.get_running_loop()
        avl_parquet_tasks = [loop.run_in_executor(custom_executor, convert_avl_to_parquet, current, environment) for current in avl_parquet]
        timetable_parquet_tasks = [loop.run_in_executor(custom_executor, convert_to_parquet, current, environment) for current in timetable_parquet]
        await asyncio.gather(*avl_parquet_tasks,*timetable_parquet_tasks)
    
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
    if subset:
        regenerate_timetables = True
    else:
        if timetable_export_needed or avl_export_needed:
            regenerate_timetables = get_boolean_input(
                "Should timetable data be re-generated before export?"
            )
    
    if regenerate_timetables:
        print("Will regenerate timetables")

    db_password = get_db_password(environment)

    asyncio.run(csv_to_parquet(avl_parquet_only,timetable_parquet_only))

    async def csv_export(export_tasks: list):
        await asyncio.gather(*export_tasks)

    env = os.environ.copy()
    env["SIRIVM_BUCKET"] = sirivm_bucket
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    script_path = os.path.join(root_dir,"sirivm_otp_matching_function", "sirivm_otp_matching_function", "historic_matching.py")
    working_dir = os.path.join(root_dir, "ingestion_pipelines","sirivm_otp_matching_function")

    summaries_to_run = []
    failed_summaries = []
    avl_exported = []

    process_date_array = sorted(process_dates)
    while (
        process_date_array
        or running_tasks
        or summaries_to_run
    ):
        avl_parquet_tasks=[]
        timetable_parquet_tasks=[]
        export_task=[]
        if process_date_array and len(running_tasks) < MAX_CONCURRENT_MATCHING_TASKS:
            process_date = process_date_array.pop(0)
            next_day = process_date + timedelta(days=1)
            if process_date in avl_export_needed:
                export_task.append(asyncio.to_thread(avl_export2,db_password, db_host, process_date, sql_list_journeys))
                timetable_export_needed = sorted({*timetable_export_needed, process_date})
                avl_parquet_tasks.append(process_date)
            
            if next_day in avl_export_needed and next_day not in avl_exported:
                export_task.append(asyncio.to_thread(avl_export2,db_password, db_host, next_day, sql_list_journeys))
                avl_exported.append(next_day)
                avl_parquet_tasks.append(next_day)

            if process_date in timetable_export_needed:
                if regenerate_timetables:
                    timetable_generation(
                        db_password, db_host, process_date, environment, subset
                    )
                export_task.append(asyncio.to_thread(timetable_export2,db_password, db_host, process_date, subset, sql_list_journeys))
                timetable_parquet_tasks.append(process_date)

            asyncio.run(csv_export(export_task))
            asyncio.run(csv_to_parquet(avl_parquet_tasks,timetable_parquet_tasks))
            if is_local:
                env["PROCESS_DATE"] = process_date.strftime("%Y-%m-%d")
                env["POSTGRES_HOST"] = "127.0.0.1"
                env["POSTGRES_PORT"] = "15432"
                env["POSTGRES_USER"] = DB_USER
                env["POSTGRES_DB"] = "abods"
                env["LOCAL_DB_PASSWORD"]= db_password
                subprocess.run(
                    ["python","-m", "sirivm_otp_matching_function.historic_matching"],
                    cwd=working_dir,
                    env=env,
                    check=True
                )
            else:
                start_historic_matching(process_date, environment)
            print(
                        f"{current_time_london().isoformat()}: Dates still queued for matching: {';'.join(d.isoformat() for d in process_date_array)}"
                    )

        if not is_local:
            look_for_existing_tasks(environment)

        completed_dates = check_for_completed_tasks(environment)
        
        if skip_summary_generation:
            sleep(60)
            continue
        
        summaries_to_run = sorted({*summaries_to_run, *completed_dates})
        if completed_dates:
            print(
                f"{current_time_london().isoformat()}: Dates queued for summary generation: {';'.join(d.isoformat() for d in summaries_to_run)}"
            )

            # Need to start more tasks before doing summary generation
            continue

        if summaries_to_run and not in_service_hours():
            process_date = summaries_to_run.pop(0)
            try:
                summary_generation(db_password, db_host, process_date, subset)
            except CalledProcessError as e:
                print(e)
                failed_summaries = sorted({*failed_summaries, process_date})
            if failed_summaries:
                print(
                    f"{current_time_london().isoformat()}: The following dates have failed summary generation: {';'.join(d.isoformat() for d in failed_summaries)}"
                )
            if summaries_to_run:
                print(
                    f"{current_time_london().isoformat()}: Dates queued for summary generation: {';'.join(d.isoformat() for d in summaries_to_run)}"
                )
            continue

        sleep(60)


    print("All processing complete")
    if failed_summaries:
        print(
            f"{current_time_london().isoformat()}: The following dates have failed summary generation, you may want to re-run them: {';'.join(d.isoformat() for d in failed_summaries)}"
        )


if __name__ == "__main__":
    main()
