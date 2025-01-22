#!/usr/bin/env python3
from datetime import datetime
import subprocess
from datetime import date, timedelta
from getpass import getpass
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
        status = containers[0]["lastStatus"]
        arn = containers[0]["taskArn"]
        process_date = [var["value"] for var in task["overrides"]["containerOverrides"][0]["environment"] if
                      var["name"] == "PROCESS_DATE"][0]
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


task_status = {}


def start_task(current: date, environment: str):
    run_output = run_matching(current, environment)
    for task_arn, status, process_date in parse_task_output(run_output):
        task_status[task_arn] = {
            "status": status,
            "process_date": process_date,
        }
        cloudwatch = f"https://eu-west-2.console.aws.amazon.com/cloudwatch/home?region=eu-west-2#logsV2:log-groups/log-group/$252Faws$252Fecs$252Fabods-{environment}/log-events/historic-matching$252Fmatcher$252F{task_arn.split('/')[-1]}"
        print(
            f"{datetime.now().isoformat()}: {process_date} started. You can read the logs at {cloudwatch}")


def look_for_existing_tasks(environment: str):
    arns = boto3.client("ecs").list_tasks(cluster=f"abods-{environment}")["taskArns"]
    status_output = get_task_status(environment, arns)
    for task_arn, status, process_date in parse_task_output(status_output):
        print(f"{datetime.now().isoformat()}: {task_arn} for date {process_date} is {status}")
        task_status[task_arn] = {
            "status": status,
            "process_date": process_date,
        }


def summary_generation(db_password: str, process_date: str):
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
            f"CALL historic_matching_summary_generation('{process_date}');",
        ],
        env={"PGPASSWORD": db_password},
        check=True,
    )


def wait_for_tasks(environment: str, db_password: str, max_tasks: int):
    while True:
        if len(task_status) < max_tasks:
            return
        status_output = get_task_status(environment, list(task_status))
        for task_arn, status, process_date in parse_task_output(status_output):
            if task_status[task_arn]["status"] != status:
                print(f"{datetime.now().isoformat()}: {task_arn} for date {process_date} is {status}")
            task_status[task_arn]["status"] = status

        for arn in list(task_status):
            status = task_status[arn]["status"]
            process_date = task_status[arn]["process_date"]
            if status in ("STOPPED", "DELETED"):
                del task_status[arn]
                try:
                    summary_generation(db_password, process_date)
                except CalledProcessError as e:
                    print(e)
                    summary_generation(db_password, process_date)
                continue
        sleep(60)


def main():
    while True:
        try:
            current = date.fromisoformat(
                input("Enter start date in yyyy-mm-dd format: ")
            )
            break
        except ValueError:
            print("Incorrect data format, should be YYYY-MM-DD")
    while True:
        try:
            end = date.fromisoformat(input("Enter end date in yyyy-mm-dd format: "))
            break
        except ValueError:
            print("Incorrect data format, should be YYYY-MM-DD")
    while True:
        environment = input("Which environment?: ")
        if environment == "sandbox":
            break
        if environment == "prod":
            break

    db_password = getpass(f"Enter password for database user {db_user}: ")

    look_for_existing_tasks(environment)
    for arn in list(task_status):
        process_date = date.fromisoformat(task_status[arn]["process_date"])
        if process_date >= current:
            current = process_date + timedelta(days=1)

    while current <= end:
        wait_for_tasks(environment, db_password, max_tasks=4)
        start_task(current, environment)
        current = current + timedelta(days=1)

    wait_for_tasks(environment, db_password, max_tasks=0)


if __name__ == "__main__":
    main()
