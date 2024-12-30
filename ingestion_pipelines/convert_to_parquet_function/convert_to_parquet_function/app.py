import os
from typing import Any

import pyarrow as pa
import pyarrow.csv as pv
import pyarrow.parquet as pq
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from dateutil.parser import parse
from pyarrow import fs

# Input data is from the public.historic_timetable_export procedure in the database
timetable_cols = [
    "group_id",
    "stop_index",
    "stop_latitude",
    "stop_longitude",
    "expected_departure_time",
    "timetable_id",
    "date_of_journey",
    "direction",
    "operator_noc",
]

timetable_superfluous_cols = []

# Input data is from the public.historic_avl_export procedure in the database
avl_cols = [
    "group_id",
    "recorded_at_time",
    "response_time_stamp",
    "latitude",
    "longitude",
    "line_name",
    "operator_ref",
    "vehicle_ref",
    "journey_ref",
    "direction_ref",
    "date_of_journey",
    "origin_ref",
    "destination_ref",
    "departure_time",
]

# We don't need these for historic matching
avl_superfluous_cols = [
    "origin_ref",
    "destination_ref",
    "departure_time",
]

logger = Logger()

s3_fs = fs.S3FileSystem(region=os.environ.get("AWS_REGION", "eu-west-2"))
s3_bucket = os.environ.get("EXPORTER_BUCKET")


def get_s3_path(path: str) -> str:
    return f"{s3_bucket}/{path}"


def lambda_handler(event: dict[str, Any], _: LambdaContext) -> dict:
    process_date = parse(event.get("process_date"))
    pd_year = process_date.year
    pd_month = str(process_date.month).zfill(2)
    pd_day = str(process_date.day).zfill(2)

    output = {
        "statusCode": 200,
        "timetable": {"processed": False},
        "avl": {"processed": False},
    }

    if event.get("skip_timetable") != "true":
        base_input_path = get_s3_path(
            f"historic/csv/timetable/YYYY={pd_year}/MM={pd_month}/{pd_year}-{pd_month}-{pd_day}.csv",
        )
        if not s3_fs.get_file_info(base_input_path).is_file:
            output["timetable"]["input_missing"] = True
        else:
            output_path = get_s3_path(
                f"historic/parquet/YYYY={pd_year}/MM={pd_month}/DD={pd_day}/timetable_{pd_year}{pd_month}{pd_day}.parquet",
            )
            if (
                event.get("overwrite_existing_output") != "true"
                and s3_fs.get_file_info(output_path).is_file
            ):
                output["timetable"]["output_exists"] = True
            else:
                stream_and_convert(
                    input_path=base_input_path,
                    input_columns=timetable_cols,
                    output_path=output_path,
                    columns_to_drop=timetable_superfluous_cols,
                )
                output["timetable"]["processed"] = True

    if event.get("skip_avl") != "true":
        base_input_path = get_s3_path(
            f"historic/csv/siri/YYYY={pd_year}/MM={pd_month}/siri_vm_{pd_year}-{pd_month}-{pd_day}.csv",
        )
        if not s3_fs.get_file_info(base_input_path).is_file:
            output["avl"]["input_missing"] = True
        else:
            output_path = get_s3_path(
                f"historic/parquet/YYYY={pd_year}/MM={pd_month}/DD={pd_day}/siri_vm_{pd_year}{pd_month}{pd_day}.parquet",
            )
            if (
                event.get("overwrite_existing_output") != "true"
                and s3_fs.get_file_info(output_path).is_file
            ):
                output["avl"]["output_exists"] = True
            else:
                stream_and_convert(
                    input_path=base_input_path,
                    input_columns=avl_cols,
                    output_path=output_path,
                    columns_to_drop=avl_superfluous_cols,
                )
                output["avl"]["processed"] = True

    return output


def stream_and_convert(
    input_path: str,
    input_columns: list[str],
    output_path: str,
    columns_to_drop: list[str],
) -> None:
    paths = [input_path]
    part = 2
    while True:
        extra_data_path = input_path + "_part" + str(part)
        if not s3_fs.get_file_info(extra_data_path).is_file:
            logger.info(f"Did not find {extra_data_path}")
            break
        if part == 10:  # noqa: PLR2004 not really a magic value, just not sure what happens when we reach 2 chars
            raise Exception(  # noqa: TRY002 Not interested for now
                "There are more parts to the data than the script has been written to handle",
            )
        logger.info(f"Found {extra_data_path}")
        paths.append(extra_data_path)
        part = part + 1

    logger.info(f"Converting {input_path} --> [{output_path}]")
    schema = pa.schema(
        [(col, pa.string()) for col in input_columns if col not in columns_to_drop],
    )
    batch_id = 0

    with (
        s3_fs.open_output_stream(output_path) as output_stream,
        pq.ParquetWriter(output_stream, schema) as writer,
    ):
        for file_path in paths:
            logger.info(f"Processing {file_path}")
            with (
                s3_fs.open_input_stream(file_path) as input_stream,
                pv.open_csv(
                    input_stream,
                    read_options=pv.ReadOptions(
                        block_size=150 * 1_000_000,
                        column_names=input_columns,
                    ),
                    parse_options=pv.ParseOptions(delimiter=",", quote_char='"'),
                    convert_options=pv.ConvertOptions(column_types=schema),
                ) as reader,
            ):
                for batch in reader:
                    batch_id += 1
                    logger.info(f"Writing batch {batch_id}")
                    writer.write_batch(batch.drop_columns(columns_to_drop))
