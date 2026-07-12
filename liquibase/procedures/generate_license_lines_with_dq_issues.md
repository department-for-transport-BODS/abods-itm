# generate_license_lines_with_dq_issues.sql

## Overview
This procedure populates the `license_line_data_quality_issues` table with records of license lines that have data quality issues, based on timetable and OTC service data. It truncates the table and inserts new records for the specified date range.

## Procedure Inputs
- **partition_date (date)**: The date used to determine the relevant timetable data for the analysis.

## Steps
1. **Truncate Data Quality Issues Table**
   - Truncates the `license_line_data_quality_issues` table to remove all existing records.

2. **Insert New Data Quality Issues**
   - Aggregates data from `otc_service` and `Timetable` tables to identify license lines with data quality issues, such as:
     - Service numbers with spaces, length > 4, or non-alphanumeric characters.
     - Timetable records within the last 8 days.
   - Inserts the identified issues into the data quality issues table.

3. **Logging**
   - Logs notices before and after the process for traceability.

---
This procedure is used to maintain up-to-date records of license lines with data quality issues for reporting and remediation.