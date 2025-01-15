import json
import os
import pathlib
from collections.abc import Sequence
from unittest import mock

from ..live_timetable_store import LiveTimetableStore
from ..matching import match_group_id_avls
from ..models import RecordToAdd, parse_live_avl_data


def run_historic_matching_test(
    test_file_path: str,
    expected_matches: Sequence[RecordToAdd],
) -> None:
    directory = pathlib.Path(test_file_path).parent

    with open(directory / "timetable.json") as f:
        timetable = json.load(f)
    with open(directory / "avl.csv") as csvfile:
        avl_list = parse_live_avl_data(csvfile, has_header=True)

    with mock.patch.dict(os.environ, {"ENABLE_ESTIMATED_MATCHING": "true"}):
        to_set, _, __ = match_group_id_avls(LiveTimetableStore(timetable), avl_list)

    assert to_set == expected_matches
