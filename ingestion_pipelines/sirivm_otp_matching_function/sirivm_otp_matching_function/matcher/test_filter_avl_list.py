import pytest

from ..client_s3 import filter_avl_list
from ..shards import shards
from .models import LiveAVLRecord

shard_0_operator_id = shards["0"][0]
shard_1_operator_id = shards["1"][0]
avl_list = [
    {"operator_ref": shard_0_operator_id},
    {"operator_ref": shard_1_operator_id},
    {"operator_ref": "TEST"},  # TEST hashes to 0
    {"operator_ref": "XXXX"},  # XXXX hashes to 4
]


@pytest.mark.parametrize(
    ("shard_id", "expected_result"),
    [
        pytest.param("0", [avl_list[0], avl_list[2]]),
        pytest.param("1", [avl_list[1]]),
        pytest.param("2", []),
        pytest.param("3", []),
        pytest.param("4", [avl_list[3]]),
        pytest.param("5", []),
        pytest.param("6", []),
    ],
)
def test_filter(shard_id: str, expected_result: list[LiveAVLRecord]) -> None:
    assert list(filter_avl_list(shard_id, avl_list)) == expected_result
