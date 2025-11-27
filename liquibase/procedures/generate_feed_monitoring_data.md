# generate_feed_monitoring_data.sql

## Overview
This procedure generates per-minute feed monitoring statistics for a specified time range, either for a whole day or a specific hour. It creates temporary tables for expected journeys and aggregates statistics for each hour in the range.

## Procedure Inputs
- **start_point (timestamp with time zone, default: start of previous hour)**: The timestamp used to determine the time range for monitoring.
- **whole_day (boolean, default: false)**: Whether to generate data for the whole day or just a specific hour.

## Steps
1. **Set Time Boundaries**
   - Determines the start and end times for the monitoring period based on `start_point` and `whole_day`.

2. **Loop Over Hours in Range**
   - For each hour in the range, sets `start_time` and `end_time`.

3. **Create Temporary Table for Expected Journeys**
   - Drops and recreates a temporary table `feedmon_temp_expected_journeys` for each hour.
   - Populates it with expected journey data for the hour.

4. **Aggregate and Store Per-Minute Statistics**
   - (Further steps in the procedure would aggregate and store per-minute statistics for the hour, using the temporary table and other relevant data sources.)

5. **Logging**
   - Logs notices for traceability at key steps.

---
This procedure is used to generate detailed feed monitoring statistics for reporting and analysis.