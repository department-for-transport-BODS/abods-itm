#!/usr/bin/env python3
import json
from datetime import datetime
import subprocess
from datetime import date, timedelta
from subprocess import CalledProcessError
from time import sleep

import boto3

db_host = "abods-prod-db.cluster-cpwu8ksu6zyo.eu-west-2.rds.amazonaws.com"
db_user = "root"


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


def start_task(current: date, environment: str):
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
    status_output = get_task_status(environment, arns)
    for task_arn, status, process_date in parse_task_output(status_output):
        print(
            f"{datetime.now().isoformat()}: {task_arn} for date {process_date.isoformat()} is {status}"
        )
        running_tasks[task_arn] = {
            "status": status,
            "process_date": process_date,
        }


def summary_generation(db_password: str, process_date: date):
    def call_process():
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
                f"CALL historic_matching_summary_generation('{process_date.isoformat()}');",
            ],
            env={"PGPASSWORD": db_password},
            check=True,
        )

    try:
        call_process()
    except CalledProcessError as e:
        # retry once
        print(e)
        call_process()


def cloudwatch_logs_link(arn: str, environment: str):
    return f"https://eu-west-2.console.aws.amazon.com/cloudwatch/home?region=eu-west-2#logsV2:log-groups/log-group/$252Faws$252Fecs$252Fabods-{environment}/log-events/historic-matching$252Fmatcher$252F{arn.split('/')[-1]}"


def check_for_completed_tasks(environment: str):
    status_output = get_task_status(environment, list(running_tasks))
    for task_arn, status, process_date in parse_task_output(status_output):
        if running_tasks[task_arn]["status"] != status:
            print(
                f"{datetime.now().isoformat()}: {task_arn} for date {process_date.isoformat()} is {status}"
            )
        running_tasks[task_arn]["status"] = status

    completed_dates: list[date] = []
    for arn in list(running_tasks):
        status = running_tasks[arn]["status"]
        process_date = running_tasks[arn]["process_date"]
        if status in ("STOPPED", "DELETED"):
            completed_dates.append(process_date)
            del running_tasks[arn]
            cloudwatch = cloudwatch_logs_link(arn, environment)
            print(
                f"{datetime.now().isoformat()}: {process_date.isoformat()} finished. You can read the logs at {cloudwatch}"
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
            process_dates = {date.fromisoformat(date_val) for date_val in process_dates}
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
        process_date = date.fromisoformat(running_tasks[arn]["process_date"])

        if process_date in process_dates:
            process_dates.remove(process_date)
        else:
            print(
                f"Found a task for {process_date.isoformat()} in {running_tasks[arn]['status']} state, "
                f"but it is not in the list of dates to run, be sure to run summary generation when it is finished with "
                f"\"CALL historic_matching_summary_generation('{process_date.isoformat()}');\""
            )

    print("Will run for the following dates")
    dates_to_start = sorted(process_dates)
    print(";".join(d.isoformat() for d in dates_to_start))

    db_password = get_db_password(environment)

    max_tasks = 5
    summaries_to_run = []
    while dates_to_start or running_tasks or summaries_to_run:
        if dates_to_start and len(running_tasks) < max_tasks:
            start_task(dates_to_start.pop(0), environment)
            dates_to_start_str = ";".join(d.isoformat() for d in dates_to_start)
            print(
                f"{datetime.now().isoformat()}: Dates still queued for matching: {dates_to_start_str}"
            )

            # Keep starting tasks if there's more we can run
            continue

        completed_dates = check_for_completed_tasks(environment)
        summaries_to_run = sorted({*summaries_to_run, *completed_dates})
        if completed_dates:
            summaries_to_run_str = ";".join(d.isoformat() for d in summaries_to_run)
            print(
                f"{datetime.now().isoformat()}: Dates queued for summary generation: {summaries_to_run_str}"
            )

            # Need to start more tasks before doing summary generation
            continue

        if summaries_to_run:
            process_date = summaries_to_run.pop(0)
            try:
                summary_generation(db_password, process_date)
            except CalledProcessError as e:
                print(e)
                summary_generation(db_password, process_date)
            summaries_to_run_str = ";".join(d.isoformat() for d in summaries_to_run)
            print(
                f"{datetime.now().isoformat()}: Dates queued for summary generation: {summaries_to_run_str}"
            )
            continue

        # If we got here then all we did was check status of tasks, and found none finished, so wait before going again
        sleep(60)


if __name__ == "__main__":
    main()
