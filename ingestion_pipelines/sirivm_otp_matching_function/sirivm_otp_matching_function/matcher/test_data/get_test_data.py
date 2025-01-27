"""Helpers to Load Test Data from Files"""

import json
from collections.abc import Sequence
from pathlib import Path

from ..models import AVLRecord, Timetable, parse_live_avl_data

test_data_dir = Path(__file__).parent


def read_timetable(file_name: str) -> Timetable:
    with open(test_data_dir / "timetable" / file_name) as f:
        return json.load(f)


def read_avl(file_name: str) -> Sequence[AVLRecord]:
    with open(test_data_dir / "avl" / file_name) as csvfile:
        return list(parse_live_avl_data(csvfile, has_header=True))
