
# summary_by_services.sql

## Overview
This procedure creates a daily partition for the `timetable_summary_service_tz` table and populates it with detailed summary statistics for services for a given date. It aggregates journey data by service, hour, and other dimensions, supporting performance analysis and reporting for public transport services.

## Procedure Inputs
- **partition_date** (`date`, default: yesterday): The date for which to generate the service summary.

## Step-by-Step Logic

### 1. Set Partition Table Name
- Constructs the partition table name as `timetable_summary_service_tz_YYYY_MM_DD` for the specified date.

### 2. Check for Timetable Data
- Checks if timetable data exists for the specified date in the `Timetable` table.
- If no timetable data exists, logs a notice and exits the procedure.

### 3. Create Partition Table if Needed
- If timetable data exists, creates a partition for the specified date if it does not already exist, as a child of `timetable_summary_service_tz` for the date range `[partition_date, partition_date + 1 day)`.
- Sets the table owner to `abods_rw`.

### 4. Delete Existing Data
- Deletes any existing data in the partition to ensure only fresh data is inserted for the day.

### 5. Insert Aggregated Summary Data
- Aggregates journey data from `timetable_summary_stops_tz` joined with `expected_services` by service, hour, and other dimensions, for the specified date.
- Calculates and inserts the following statistics for each group:
  - `on_time_count`, `early_count`, `late_count`: Counts of journeys by punctuality
  - `completed`, `scheduled`: Number of completed and scheduled journeys
  - `is_timing_point`: Timing point flag
  - `max_early`, `max_late`: Maximum early/late values
  - `avg_time_difference`: Average time difference (weighted by completed journeys)
  - `admin_areas`: Administrative areas (from `expected_services`)
  - `estimated`: Whether the record is estimated
  - `direction`: Journey direction
  - `count_delayed`, `average_delay`: Delay statistics (weighted average)
  - `incomplete_reason`: Reason for incomplete journeys
- Uses subqueries to calculate weighted averages for time difference and delay.

### 6. Logging and Ownership
- Logs notices at key steps for traceability (partition creation, data deletion, data insertion).
- Sets the procedure owner to `abods_proxy_rw`.

## Outputs
- The partitioned table `timetable_summary_service_tz_YYYY_MM_DD` is created/updated for the specified date, containing detailed summary records for each service and hour.
- Each record includes:
  - `operator_noc`, `line_name`, `noc_and_line_and_servicecode`, `date_of_journey`, `departure_hour`, `departure_hour_only`, `day_of_week`, `on_time_count`, `early_count`, `late_count`, `completed`, `scheduled`, `is_timing_point`, `max_early`, `max_late`, `avg_time_difference`, `admin_areas`, `estimated`, `direction`, `count_delayed`, `average_delay`, `incomplete_reason`

## Notes
- This procedure is typically run as part of a daily ETL or data warehousing process to maintain up-to-date service summary statistics.
- Uses dynamic SQL for partition management and data insertion.
- Ensures that only data for the specified date is included in the summary.

---
This procedure is essential for maintaining partitioned, query-efficient service summary data for performance analysis and reporting.