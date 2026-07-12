# update_performance_statistics_v4.sql

## Overview
This procedure updates the `performance_statistics` table with new statistics for various periods and timing point configurations. It deletes old statistics, calculates new ones for current and trend periods, and inserts the results into the summary table.

## Procedure Inputs
- **None**

## Steps
1. **Delete Old Statistics**
   - Deletes all records from the `performance_statistics` table.

2. **Iterate Over Period Types and Timing Point Configurations**
   - For each period type (e.g., last 7 days, last 28 days, month to date, last month) and timing point configuration (true/false):
     - Calls `get_date_range` and `get_trend_date_range` to determine the relevant date ranges.
     - Creates temporary tables for current and trend statistics.
     - Aggregates journey data and calculates summary statistics for each configuration.

3. **Insert New Statistics**
   - Inserts the calculated statistics into the `performance_statistics` table.

4. **Logging**
   - Logs notices at key steps for traceability.

---
This procedure is used to maintain up-to-date performance statistics for reporting and analysis.