"""Helpers to Load Test Data from Files"""

import csv
import json
from collections.abc import Iterable, Sequence
from pathlib import Path

from ...client_s3 import live_avl_column_parsers, parse_live_avl_row
from ..models import AVLRecord, LiveAVLRecord, Timetable

test_data_dir = Path(__file__).parent


def parse_test_avl_file(
    stream: Iterable[str],
) -> Iterable[LiveAVLRecord]:
    """Parse live avl csv data into LiveAVLRecord dicts"""
    for row in csv.DictReader(stream):
        yield parse_live_avl_row(row)


def read_timetable(file_name: str) -> Timetable:
    with open(test_data_dir / "timetable" / file_name) as f:
        return json.load(f)


def read_avl(file_name: str) -> Sequence[AVLRecord]:
    with open(test_data_dir / "avl" / file_name) as csvfile:
        return list(parse_test_avl_file(csvfile))
