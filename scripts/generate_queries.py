"""Utility script for generating a bunch of SQL CALL queries for multiple dates"""

from datetime import datetime, timedelta

fn = "historic_avl_export"
from_date = "2024-11-23"
to_date = "2024-11-28"

if __name__ == "__main__":
    current = datetime.fromisoformat(from_date)
    while current <= datetime.fromisoformat(to_date):
        print(f"CALL public.{fn}('{current.strftime("%Y-%m-%d")}');")
        current = current + timedelta(days=1)
