# update_distinct_routes.sql

## Overview
This procedure updates the `distinct_routes` and `servicepattern_route` tables with new route information for a given date. It calculates distinct routes from the timetable, inserts them into the relevant tables, and analyzes the results.

## Procedure Inputs
- **partition_date (date)**: The date for which to update distinct routes.

## Steps
1. **Create Temporary Table for Route Calculations**
   - Drops and recreates a temporary table `temp_distinct_route_calc`.
   - Aggregates distinct route information from the `Timetable` table for the specified date.

2. **Insert New Distinct Routes**
   - Inserts new distinct routes into the `distinct_routes` table, avoiding duplicates.

3. **Analyze Distinct Routes Table**
   - Runs analysis on the `distinct_routes` table to optimize performance.

4. **Insert Service Pattern Route Matches**
   - Inserts new matches between distinct routes and service codes into the `servicepattern_route` table, avoiding duplicates.

5. **Logging**
   - Logs notices at key steps for traceability.

---
This procedure is used to maintain up-to-date route and service pattern information for analysis and reporting.