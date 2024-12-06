import os
from typing import Any

import pyarrow as pa
import pyarrow.csv as pv
import pyarrow.parquet as pq
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from dateutil.parser import parse
from pyarrow import fs

avl_csv_schema = pa.schema(
    [
        ("siri_vm_positions_id", pa.string()),
        ("operator_ref", pa.string()),
        ("line_name", pa.string()),
        ("journey_ref", pa.string()),
        ("direction_ref", pa.string()),
        ("date_of_journey", pa.string()),
        ("latitude", pa.string()),
        ("longitude", pa.string()),
        ("vehicle_ref", pa.string()),
        ("batch_id", pa.string()),
        ("recorded_at_time", pa.string()),
        ("response_time_stamp", pa.string()),
        ("load_time_stamp", pa.string()),
        ("group_id", pa.string()),
        ("origin_ref", pa.string()),
        ("destination_ref", pa.string()),
        ("departure_time", pa.string()),
    ]
)

timetable_csv_schema = pa.schema(
    [
        ("group_id", pa.string()),
        ("stop_index", pa.string()),
        ("stop_latitude", pa.string()),
        ("stop_longitude", pa.string()),
        ("expected_departure_time", pa.string()),
        ("timetable_id", pa.string()),
        ("date_of_journey", pa.string()),
        ("direction", pa.string()),
    ]
)

timetable_cols = [
    "group_id",
    "stop_index",
    "stop_latitude",
    "stop_longitude",
    "expected_departure_time",
    "timetable_id",
    "date_of_journey",
    "direction",
]

avl_cols = [
    "siri_vm_positions_id",
    "operator_ref",
    "line_name",
    "journey_ref",
    "direction_ref",
    "date_of_journey",
    "latitude",
    "longitude",
    "vehicle_ref",
    "batch_id",
    "recorded_at_time",
    "response_time_stamp",
    "load_time_stamp",
    "group_id",
    "origin_ref",
    "destination_ref",
    "departure_time",
]

logger = Logger()


def lambda_handler(event: dict[str, Any], _: LambdaContext) -> None:
    s3_bucket = "abods-sandbox-exporter-bucket"
    s3_fs = fs.S3FileSystem(region=os.environ.get("AWS_REGION", "eu-west-1"))
    process_date = parse(event.get("process_date"))
    pd_year = process_date.year
    pd_month = str(process_date.month).zfill(2)
    pd_day = str(process_date.day).zfill(2)
    part_2 = event.get("part_2")
    is_timetable = event.get("is_timetable")
    local_parquet = f"historic/parquet/YYYY={pd_year}/MM={pd_month}/DD={pd_day}/siri_vm_{pd_year}{pd_month}{pd_day}.parquet"
    csv_files = [
        f"historic/csv/siri/YYYY={pd_year}/MM={pd_month}/siri_vm_{pd_year}{pd_month}{pd_day}.csv"
    ]
    if part_2:
        csv_files = [
            f"historic/csv/siri/YYYY={pd_year}/MM={pd_month}/siri_vm_{pd_year}{pd_month}{pd_day}.csv",
            f"historic/csv/siri/YYYY={pd_year}/MM={pd_month}/siri_vm_{pd_year}{pd_month}{pd_day}.csv_part2",
        ]
    schema = avl_csv_schema
    column_names = avl_cols
    if is_timetable:
        schema = timetable_csv_schema
        column_names = timetable_cols
        csv_files = [
            f"historic/csv/timetable/YYYY={pd_year}/MM={pd_month}/{pd_year}-{pd_month}-{pd_day}.csv"
        ]
        local_parquet = f"historic/parquet/YYYY={pd_year}/MM={pd_month}/DD={pd_day}/timetable_{pd_year}{pd_month}{pd_day}.parquet"
    batch_id = 0
    output_path = f"{s3_bucket}/{local_parquet}"
    logger.info(f"Converting {csv_files} --> [{output_path}]")

    # Read the CSV file from S3
    with (
        s3_fs.open_output_stream(output_path) as output_stream,
        pq.ParquetWriter(output_stream, schema) as writer,
    ):
        for csv_file in csv_files:
            input_path = f"{s3_bucket}/{csv_file}"
            with s3_fs.open_input_stream(input_path) as input_stream:
                logger.info(f"Processing {input_path}")
                csv_stream = pv.open_csv(
                    input_stream,
                    read_options=pv.ReadOptions(
                        block_size=150 * 1000000, column_names=column_names
                    ),
                    parse_options=pv.ParseOptions(delimiter=",", quote_char='"'),
                    convert_options=pv.ConvertOptions(column_types=schema),
                )
                for batch in csv_stream:
                    batch_id += 1
                    logger.info(f"Writing batch {batch_id}")
                    writer.write_batch(batch)
                csv_stream = None

    return {
        "statusCode": 200,
    }
