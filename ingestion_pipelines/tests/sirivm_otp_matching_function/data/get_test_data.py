"""
Helpers to Load Test Data from Files
"""

import importlib.util
from pathlib import Path
import json
import csv

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
        avl_dicts.append([avl])
    return avl_dicts


def get_shards(file_name: str) -> dict:
    path = test_data_dir / file_name
    with Path.open(path) as f:
        shards = json.load(f)
    return shards
