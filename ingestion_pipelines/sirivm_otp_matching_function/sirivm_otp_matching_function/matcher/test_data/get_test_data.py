"""Helpers to Load Test Data from Files"""

import json
from pathlib import Path

import pandas as pd

from ingestion_pipelines.sirivm_otp_matching_function.sirivm_otp_matching_function.matcher.models import (
    AVLRecord,
    Timetable,
    live_avl_file_columns,
)

test_data_dir = Path(__file__).parent


def read_timetable(file_name: str) -> Timetable:
    path = test_data_dir / "timetable" / file_name
    with Path.open(path) as f:
        return json.load(f)


def read_avl(file_name: str) -> list[AVLRecord]:
    path = test_data_dir / "avl" / file_name
    data = pd.read_csv(path, dtype=live_avl_file_columns, header=0)
    data["line_name"] = data["line_name"].fillna("")
    data["direction_ref"] = data["direction_ref"].fillna("")

    return data.to_dict("records")
