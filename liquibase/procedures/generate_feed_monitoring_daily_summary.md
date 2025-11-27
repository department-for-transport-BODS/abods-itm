# generate_feed_monitoring_daily_summary.sql

## Overview
This procedure generates a daily summary of feed monitoring data for each operator for a given date. It calculates update frequency and availability metrics, stores them in a temporary table, and then inserts the results into the `feed_monitor_daily_summary` table. Old summary data (older than 3 months) is also purged.

## Procedure Inputs
- **start_point (timestamp with time zone, default: start of yesterday)**: The timestamp used to determine the day for which to generate the summary. Defaults to the start of the previous day.

## Steps
1. **Determine Journey Date**
   - Sets `journey_date` to the date part of `start_point` (truncated to day).

2. **Create Temporary Summary Table**
   - Drops and recreates a temporary table `feedmon_temp_day_summary`.
   - Aggregates data from `feed_monitor_minute_summary` for the journey date and each operator, calculating:
     - `update_frequency`: Average update frequency in minutes (null if no data).
     - `availability`: Ratio of actual to expected updates.

3. **Delete Existing Daily Summary**
   - Deletes any existing records in `feed_monitor_daily_summary` for the journey date.

4. **Insert New Daily Summary**
   - Inserts the aggregated results from the temporary table into `feed_monitor_daily_summary`.

5. **Purge Old Data**
   - Deletes records in `feed_monitor_daily_summary` older than 3 months.

---
This procedure is used to maintain up-to-date daily feed monitoring statistics for each operator.