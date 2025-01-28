"""Route with avl data more than 2 hours early"""

from ..util import run_historic_matching_test

matches = []


def test_historic_match() -> None:
    assert run_historic_matching_test(__file__) == matches
