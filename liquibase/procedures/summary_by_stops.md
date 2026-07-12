
# summary_by_stops.sql

## Overview
This procedure creates a daily partition for the `timetable_summary_stops_tz` table and populates it with detailed summary statistics for stops for a given date. It aggregates journey and stop data, supporting performance analysis and reporting at the stop level for public transport services.

## Procedure Inputs
- **partition_date** (`date`, default: yesterday): The date for which to generate the stop summary.

## Step-by-Step Logic

### 1. Set Partition Table Name
- Constructs the partition table name as `timetable_summary_stops_tz_YYYY_MM_DD` for the specified date.

### 2. Check for Timetable Data
- Checks if timetable data exists for the specified date (partitioned table `Timetable_pYYYY_MM_DD`).
- If no timetable data exists, logs a notice and exits the procedure.

### 3. Create Partition Table if Needed
- If timetable data exists, checks if the partition table for the date exists.
- If not, creates the partition table (unattached) with the same structure as `timetable_summary_stops_tz` and sets the owner to `abods_rw`.
- If the table exists, deletes any existing data to ensure only fresh data is inserted for the day.

### 4. Insert Aggregated Summary Data
- Aggregates journey and stop data from the partitioned timetable and expected journeys for the specified date.
- Calculates and inserts the following statistics for each group:
  - `on_time_count`, `early_count`, `late_count`: Counts of journeys by punctuality
  - `completed`, `scheduled`: Number of completed and scheduled journeys
  - `is_timing_point`: Timing point flag
  - `max_early`, `max_late`: Maximum early/late values (bucketed)
  - `avg_time_difference`: Average time difference (in minutes)
  - `estimated`: Whether the record is estimated
  - `direction`, `stop_index`, `common_name`, `locality_id`, `line_name`, `stop_latitude`, `stop_longitude`
  - `count_delayed`, `average_delay`: Delay statistics
  - `diff_sched_time_to_stop`, `diff_sched_time_to_stop_timing_point`: Scheduled time differences to previous stop/timing point
  - `diff_actual_time_to_stop`, `diff_actual_time_to_stop_timing_point`: Actual time differences to previous stop/timing point
  - `incomplete_reason`: Reason for incomplete journeys
- Uses window functions and joins to calculate previous stop/timing point times and other advanced metrics.

### 5. Attach Partition Table
- Checks if the partition table is attached to the master table `timetable_summary_stops_tz`.
- If not, attaches it for the date range `[partition_date, partition_date + 1 day)`.

### 6. Logging and Ownership
- Logs notices at key steps for traceability (partition creation, data deletion, data insertion, partition attachment).

## Outputs
- The partitioned table `timetable_summary_stops_tz_YYYY_MM_DD` is created/updated and attached for the specified date, containing detailed summary records for each stop.
- Each record includes:
  - `operator_noc`, `service_code`, `noc_and_line_and_servicecode`, `stop_id`, `locality_id`, `line_name`, `stop_latitude`, `stop_longitude`, `date_of_journey`, `departure_hour`, `departure_hour_only`, `day_of_week`, `on_time_count`, `early_count`, `late_count`, `completed`, `scheduled`, `common_name`, `is_timing_point`, `max_early`, `max_late`, `avg_time_difference`, `estimated`, `direction`, `stop_index`, `count_delayed`, `average_delay`, `diff_sched_time_to_stop`, `diff_sched_time_to_stop_timing_point`, `diff_actual_time_to_stop`, `diff_actual_time_to_stop_timing_point`, `incomplete_reason`

## Notes
- This procedure is typically run as part of a daily ETL or data warehousing process to maintain up-to-date stop summary statistics.
- Uses dynamic SQL, window functions, and advanced aggregation for detailed stop-level analytics.
- Ensures that only data for the specified date is included in the summary and that partitions are properly managed and attached.

---
This procedure is essential for maintaining partitioned, query-efficient stop summary data for performance analysis and reporting.