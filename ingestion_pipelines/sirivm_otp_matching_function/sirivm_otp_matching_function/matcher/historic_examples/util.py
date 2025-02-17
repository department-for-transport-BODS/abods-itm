import csv
import json
import os
import pathlib
from collections.abc import Iterable, Sequence
from unittest import mock

from ...client_s3 import live_avl_column_parsers, parse_live_avl_row
from ..live_timetable_store import LiveTimetableStore
from ..matching import match_group_id_avls
from ..models import LiveAVLRecord, NewDbMatch


def parse_test_avl_file(
    stream: Iterable[str],
) -> Iterable[LiveAVLRecord]:
    """Parse live avl csv data into LiveAVLRecord dicts"""
    for row in csv.DictReader(stream):
        yield parse_live_avl_row(row)


def run_historic_matching_test(
    test_file_path: str,
) -> Sequence[NewDbMatch]:
    directory = pathlib.Path(test_file_path).parent

    with open(directory / "timetable.json") as f:
        timetable = json.load(f)
    with open(directory / "avl.csv") as csvfile:
        avl_list = list(parse_test_avl_file(csvfile))

    with mock.patch.dict(os.environ, {"ENABLE_ESTIMATED_MATCHING": "true"}):
        to_set, _, __ = match_group_id_avls(LiveTimetableStore(timetable), avl_list)

    return to_set
