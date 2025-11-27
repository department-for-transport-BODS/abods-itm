# frequent_summary_services.sql

## Overview
This procedure populates the `timetable_frequent_summary_services` table with summary statistics for frequent services for a given date. It deletes any existing data for the date and inserts new aggregated data based on timetable information.

## Procedure Inputs
- **partition_date (date, default: yesterday)**: The date for which to generate the summary. Defaults to the previous day if not specified.

## Steps
1. **Set Table Name**
   - Sets the target table as `timetable_frequent_summary_services`.

2. **Delete Existing Data**
   - Deletes all records in the table for the specified date to ensure only fresh data is inserted.

3. **Insert New Summary Data**
   - Aggregates timetable data for the date, calculating statistics such as:
     - Maximum early/late times
     - Average time difference
     - Expected and actual headways
     - Excess wait time
     - Whether the data is estimated
     - Count of headway stops
     - Timing point flag
   - Inserts the aggregated data into the summary table.

4. **Logging**
   - Logs notices before deleting and inserting data for traceability.

---
This procedure is used to maintain up-to-date summary statistics for frequent services, supporting performance analysis and reporting.