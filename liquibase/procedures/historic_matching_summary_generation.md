# historic_matching_summary_generation.sql

## Overview
This procedure orchestrates the generation of historic matching summary data for a given date. It checks for timetable data and, if present, calls a series of other procedures to generate and populate summary tables and statistics.

## Procedure Inputs
- **partition_date (date)**: The date for which to generate the historic matching summary.

## Steps
1. **Check for Timetable Data**
   - If no timetable data exists for the date, logs a notice and exits.

2. **Call Downstream Procedures**
   - If timetable data exists, calls the following procedures in order:
     - `incomplete_data_load`
     - `generate_expected_tables`
     - `create_timetable_threshold_summary`
     - `populate_headway`
     - `summary_by_stops`
     - `frequent_summary_services`
     - `summary_by_services`
     - `summary_by_operators`
     - `populate_avl_recorded_expected_journeys`
     - `update_expected_service_distances`
   - Each call is logged for traceability.

3. **Logging**
   - Logs notices at the start and end of the process.

---
This procedure is used to coordinate the generation of historic matching summary data, ensuring all relevant tables and statistics are updated for the specified date.