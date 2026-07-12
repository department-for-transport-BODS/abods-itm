
# create_timetable_threshold_summary.sql

## Overview
This procedure creates a daily partition for the `timetable_threshold_summary` table for a specified date and populates it with detailed summary data based on expected journeys, service thresholds, and timetable records. It ensures that the summary table is partitioned, up-to-date, and ready for on-time performance (OTP) analysis and reporting.

## Procedure Inputs
- **pt_date** (`date`): The date for which the partition and summary should be created.

## Step-by-Step Logic

### 1. Set Partition Date and Table Name
- Sets `partition_date` to the input parameter `pt_date`.
- Constructs the partition table name as `timetable_threshold_summary_YYYY_MM_DD`.

### 2. Check for Timetable Data
- Checks if there is any timetable data for the partition date in the `Timetable` table.
- If no data exists, logs a notice and exits the procedure.

### 3. Create Partition Table if Needed
- If timetable data exists, creates a partition for the specified date if it does not already exist.
- The partition is created as a child of `timetable_threshold_summary` for the date range `[partition_date, partition_date + 1 day)`.
- Sets the table owner to `abods_rw`.

### 4. Delete Existing Data in Partition
- Deletes any existing data in the partition to ensure only fresh data is inserted for the day.

### 5. Prepare Temporary Table for Expected Journeys
- Drops and recreates a temporary table `temp_expected_journeys_with_service_admin_ids`.
- Populates it with expected journeys joined to expected services, filtering out cancelled journeys for the partition date.
- Includes fields: date_of_journey, operator_noc, line_name, journey_code, direction, noc_and_line_and_servicecode, service_name, admin_area_id.

### 6. Insert Aggregated Summary Data
- Inserts aggregated summary data into the partition table using a complex query that:
  - Joins timetable records with the temporary table of expected journeys.
  - Filters out frequent services and records with no time difference.
  - Groups by operator, line, service, admin area, hour, and other dimensions.
  - Calculates fields such as:
    - `time_diff_minutes`: Floor of time difference in minutes
    - `otp_count`: Count of on-time performance records
    - `estimated`: Whether the record is estimated
    - `is_timing_point`, `admin_areas`, `departure_hour`, `day_of_week`, etc.
- The inserted data supports threshold-based analysis for timetable performance.

### 7. Logging and Ownership
- Logs notices at key steps for traceability (partition creation, data deletion, data insertion).
- Sets the procedure owner to `abods_proxy_rw`.

## Outputs
- The partitioned table `timetable_threshold_summary_YYYY_MM_DD` is created/updated for the specified date, containing detailed summary records for OTP analysis.
- Each record includes:
  - `operator_noc`, `line_name`, `noc_and_line_and_servicecode`, `service_name`, `time_diff_minutes`, `date_of_journey`, `is_timing_point`, `admin_areas`, `departure_hour`, `otp_count`, `day_of_week`, `estimated`, etc.

## Notes
- The procedure is typically run as part of a daily ETL or data warehousing process to maintain up-to-date threshold summary statistics for timetables.
- Uses temporary tables and dynamic SQL for partition management and data insertion.
- Ensures that only non-cancelled, non-frequent, and valid records are included in the summary.

---
This procedure is essential for maintaining partitioned, query-efficient summary data for timetable threshold and OTP analysis.