"""Helpers to Load Test Data from Files"""

import csv
import json
from pathlib import Path

from ingestion_pipelines.sirivm_otp_matching_function.sirivm_otp_matching_function.client_s3 import (
    parse_timetable,
)

test_data_dir = Path(__file__).parent


def read_timetable(file_name: str) -> dict:
    path = test_data_dir / "timetable" / file_name
    with Path.open(path) as f:
        timetable_json = json.load(f)
    return parse_timetable(timetable_json)


def read_avl(file_name: str) -> list:
    path = test_data_dir / "avl" / file_name
    avl_reader = csv.DictReader(Path.open(path))
    avl_list = list(avl_reader)
    avl_dicts = []
    for avl in avl_list:
        avl_dicts.append([avl])  # noqa: PERF401 - BODS-7131
    return avl_dicts
