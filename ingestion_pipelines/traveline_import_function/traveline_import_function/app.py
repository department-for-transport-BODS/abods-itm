import os

import boto3
from aws_lambda_powertools import Logger
from botocore.client import BaseClient

from .shared.db import setup_db


logger = Logger()
conn = setup_db()


class TravelineImportError(RuntimeError):
    pass


def get_s3_client(region: str, role_arn: str | None) -> BaseClient:
    if not role_arn:
        return boto3.client("s3", region_name=region)

    sts = boto3.client("sts", region_name=region)
    assumed = sts.assume_role(
        RoleArn=role_arn,
        RoleSessionName="traveline-noclines-import-session",
        DurationSeconds=3600,
    )
    creds = assumed["Credentials"]

    return boto3.client(
        "s3",
        region_name=region,
        aws_access_key_id=creds["AccessKeyId"],
        aws_secret_access_key=creds["SecretAccessKey"],
        aws_session_token=creds["SessionToken"],
    )


def resolve_noclines_key(s3_client: BaseClient, bucket: str, prefix: str) -> str:
    paginator = s3_client.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=bucket, Prefix=prefix)

    target_name = "table_noclines_latest_csv.csv"
    candidates = []

    for page in pages:
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.lower().endswith(target_name):
                candidates.append(obj)

    if not candidates:
        message = f"No '{target_name}' found under s3://{bucket}/{prefix}"
        raise TravelineImportError(message)

    selected = max(candidates, key=lambda o: o["LastModified"])
    return selected["Key"]


def lambda_handler(_event: dict, _context: dict) -> None:
    bucket = os.getenv("NOC_BUCKET_NAME")
    key_prefix = os.getenv("NOC_S3_KEY")
    region = os.getenv("NOC_BUCKET_REGION")
    role_arn = os.getenv("NOC_ROLE_ARN")

    if not bucket:
        raise TravelineImportError("NOC_BUCKET_NAME environment variable must be set")
    if not key_prefix:
        raise TravelineImportError("NOC_S3_KEY environment variable must be set")
    if not region:
        raise TravelineImportError("NOC_BUCKET_REGION environment variable must be set")
    if not role_arn:
        raise TravelineImportError(
            "NOC_ROLE_ARN environment variable must be set for cross-account access",
        )