"""AVL data with no timetable"""

from ..util import run_historic_matching_test

matches = []


def test_historic_match() -> None:
    run_historic_matching_test(__file__, matches)
