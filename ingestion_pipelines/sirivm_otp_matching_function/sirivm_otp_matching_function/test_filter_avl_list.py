from .client_s3 import filter_avl_list

shard_1_operator_id = "TFLO"
shard_2_operator_id = "NATX"


def test_first_shard():
    shards = {
        "1": [shard_1_operator_id],
        "2": [shard_2_operator_id, "SCSO"],
        "3": ["BNSM"],
    }
    avl_list = [
        {"operator_ref": shard_1_operator_id},
        {"operator_ref": shard_2_operator_id},
        {"operator_ref": "TEST"},
    ]
    assert filter_avl_list("1", shards, avl_list) == [avl_list[0]]


def test_no_shard():
    shards = {
        "1": [shard_1_operator_id],
        "2": [shard_2_operator_id, "SCSO"],
        "3": ["BNSM"],
    }
    avl_list = [
        {"operator_ref": shard_1_operator_id},
        {"operator_ref": shard_2_operator_id},
        {"operator_ref": "TEST"},
    ]
    assert filter_avl_list("0", shards, avl_list) == [avl_list[2]]


def test_unknown_shard():
    shards = {
        "1": [shard_1_operator_id],
        "2": [shard_2_operator_id, "SCSO"],
        "3": ["BNSM"],
    }
    avl_list = [
        {"operator_ref": shard_1_operator_id},
        {"operator_ref": shard_2_operator_id},
        {"operator_ref": "TEST"},
    ]
    assert filter_avl_list("4", shards, avl_list) == []
