import csv
import json
import os
import pathlib
from collections.abc import Iterable, Sequence
from unittest import mock

from ..live_timetable_store import LiveTimetableStore
from ..matching import match_group_id_avls
from ..models import LiveAVLRecord, RecordToAdd

# Live avl files contain more records than we need, and the ordering is important so defined here to be explicit
live_avl_file_columns = {
    "recorded_at_time": str,
    "response_timestamp": str,
    "latitude": float,
    "longitude": float,
    "line_name": lambda x: str(x or ""),
    "operator_ref": str,
    "vehicle_ref": str,
    "journey_ref": str,
    "direction_ref": lambda x: str(x or ""),
    "date_of_journey": str,
    "batch_id": int,
}
fieldnames = list(live_avl_file_columns)


def parse_live_avl_data(stream: Iterable[str]) -> Sequence[LiveAVLRecord]:
    """Parse live avl csv data into LiveAVLRecord dicts"""
    rows = []
    for row in csv.DictReader(stream):
        for key, val in row.items():
            convert = live_avl_file_columns.get(key) or str
            row[key] = convert(val)
        rows.append(row)
    return rows


def run_historic_matching_test(
    test_file_path: str,
    expected_matches: Sequence[RecordToAdd],
) -> None:
    directory = pathlib.Path(test_file_path).parent

    with open(directory / "timetable.json") as f:
        timetable = json.load(f)
    with open(directory / "avl.csv") as csvfile:
        avl_list = parse_live_avl_data(csvfile)

    with mock.patch.dict(os.environ, {"ENABLE_ESTIMATED_MATCHING": "true"}):
        to_set, _, __ = match_group_id_avls(LiveTimetableStore(timetable), avl_list)

    assert to_set == expected_matches
