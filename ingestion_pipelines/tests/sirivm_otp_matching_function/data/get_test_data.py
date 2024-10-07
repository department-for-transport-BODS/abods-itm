"""
Helpers to Load Test Data from Files
"""

import importlib.util
from pathlib import Path
import json
import csv

test_data_dir = Path(__file__).parent

def read_timetable(file_name: str) -> dict:
    path = test_data_dir / "timetable" / file_name
    with Path.open(path) as f:
        timetable_json = json.load(f)
    return timetable_json

def read_avl(file_name: str) -> list:
    path = test_data_dir / "avl" / file_name
    avl_reader = csv.DictReader(Path.open(path))
    avl_list = list(avl_reader)
    avl_dicts = []
    for avl in avl_list:
        avl_dicts.append([avl])
    return avl_dicts

def get_shards(file_name: str) -> dict:
    path = test_data_dir / file_name
    with Path.open(path) as f:
        shards = json.load(f)
    return shards

def get_expected_result(group_id: str) -> dict:
    """
    Load Expected Result for processing entire stop history
    """
    file_path = test_data_dir / "expected" / f"{group_id}.py"
    spec = importlib.util.spec_from_file_location("module.name", file_path)
    if spec is not None:
        module = importlib.util.module_from_spec(spec)
        if spec.loader is not None:
            spec.loader.exec_module(module)
            return module.result
    raise ValueError("Could not find expected result")