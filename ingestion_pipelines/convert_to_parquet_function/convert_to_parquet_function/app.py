import os
from typing import Any

import pyarrow as pa
import pyarrow.csv as pv
import pyarrow.parquet as pq
from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from dateutil.parser import parse
from pyarrow import DataType, fs

# output schema also matches the column order of the input data from the public.historic_timetable_export procedure
timetable_output_schema = {
    "group_id": pa.string(),
    "stop_index": pa.string(),
    "stop_latitude": pa.string(),
    "stop_longitude": pa.string(),
    "expected_departure_time": pa.string(),
    "timetable_id": pa.string(),
    "date_of_journey": pa.string(),
    "direction": pa.string(),
    "operator_noc": pa.string(),
}

# output schema also matches the column order of the input data from the public.historic_avl_export procedure
avl_output_schema = {
    "group_id": pa.string(),
    "recorded_at_time": pa.date64(),
    "response_timestamp": pa.date64(),
    "latitude": pa.Float32,
    "longitude": pa.Float32,
    "line_name": pa.string(),
    "operator_ref": pa.string(),
    "vehicle_ref": pa.string(),
    "journey_ref": pa.string(),
    "direction_ref": pa.string(),
    "date_of_journey": pa.date32(),
    "origin_ref": pa.string(),
    "destination_ref": pa.string(),
    "departure_time": pa.date64(),
}

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
                    column_types=timetable_output_schema,
                    output_path=output_path,
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
                    column_types=avl_output_schema,
                    output_path=output_path,
                )
                output["avl"]["processed"] = True

    return output


def stream_and_convert(
    input_path: str,
    column_types: dict[str, DataType],
    output_path: str,
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
    batch_id = 0

    schema = pa.schema(list(column_types.items()))
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
                        column_names=list(column_types.keys()),
                    ),
                    parse_options=pv.ParseOptions(delimiter=",", quote_char='"'),
                    convert_options=pv.ConvertOptions(column_types=schema),
                ) as reader,
            ):
                for batch in reader:
                    batch_id += 1
                    logger.info(f"Writing batch {batch_id}")
                    writer.write_batch(batch)
