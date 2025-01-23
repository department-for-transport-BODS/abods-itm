#!/usr/bin/env python3

from datetime import date, timedelta

import boto3

s3 = boto3.client("s3")
paginator = s3.get_paginator("list_objects_v2")
base_prefix = "historic/"


def list_files(bucket: str, prefix: str):
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for item in page["Contents"]:
            yield item["Key"]


def main():
    while True:
        environment = input("Which environment?: ")
        if environment == "sandbox":
            break
        if environment == "prod":
            break
    bucket = f"abods-{environment}-exporter-bucket"

    files = list(list_files(bucket, base_prefix))

    current = date.fromisoformat("2024-01-01")
    end = date.fromisoformat("2025-01-01")

    while current <= end:
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
            "date": current.isoformat(),
            "timetable_csv": (timetable_csv_path in files),
            "timetable_parquet": (timetable_parquet_path in files),
            "avl_csv": avl_csv_path in files,
            "avl_gz": (avl_gz_path in files),
            "avl_parquet": (avl_parquet_path in files),
        }
        if not data["avl_csv"] and not data["avl_gz"]:
            print("CALL public.historic_avl_export('"+data["date"]+"');", end="")
        # if data["timetable_csv"] and not data["timetable_parquet"]:
        #     print(
        #         f"assume abods-prod --exec -- ./historic-matching-data-conversion.sh {data['date']} prod"
        #     )
        # if data["avl_csv"] and not data["avl_parquet"]:
        #     print(
        #         f"assume abods-prod --exec -- ./historic-matching-data-conversion.sh {data['date']} prod"
        #     )
        # if data["avl_csv"] and not data["avl_parquet"]:
        #     print(
        #         f"aws s3 cp \"s3://abods-sandbox-exporter-bucket/{avl_csv_path}\" \"s3://abods-prod-exporter-bucket/{avl_csv_path}\""
        #     )
        #
        # if data["timetable_parquet"] and data["avl_parquet"]:
        #     print(
        #         f"{data['date']}"
        #     )
        current = current + timedelta(days=1)


if __name__ == "__main__":
    main()
