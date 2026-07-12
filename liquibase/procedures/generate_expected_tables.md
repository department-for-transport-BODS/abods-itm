
# generate_expected_tables.sql

## Overview
This procedure generates and maintains several key tables and views related to expected journeys, services, and operators for a given date. It is a core ETL step for preparing journey, service, and operator data for downstream analytics, matching, and reporting.

## Procedure Inputs
- **partition_date (date)**: The date for which to generate expected journeys and related data.

## Steps
1. **Delete Existing Expected Journeys**
   - Deletes all records in `expected_journeys` for the specified date to ensure only fresh data is inserted.

2. **Insert New Expected Journeys**
   - Aggregates timetable data for the date, using window functions to:
     - Count stops per journey
     - Get the first and last expected departure times
     - Retrieve journey pattern descriptions and other metadata
   - Joins with `transmodel_servicepattern` for additional journey pattern info.
   - Inserts the aggregated data into the `expected_journeys` table, including:
     - `date_of_journey`, `operator_noc`, `line_name`, `noc_and_line_and_servicecode`, `journey_code`, `group_id`, `stop_count`, `expected_journey_start`, `journey_pattern_description`, `vehicle_journey_id`, `day_of_week`, `admin_area_id` (as array), `expected_journey_end`, `direction`.

3. **Analyze `expected_journeys` Table**
   - Runs `ANALYSE` on the table to update statistics for query planning.

4. **Delete and Insert `expected_services_by_date`**
   - Deletes all records in `expected_services_by_date` for the date.
   - Inserts new records by aggregating `expected_journeys` by service code and admin area.
   - Each service code gets an array of admin areas for the date.

5. **Analyze `expected_services_by_date` Table**
   - Runs `ANALYSE` on the table to update statistics.

6. **Upsert into `service_details`**
   - For each service code, upserts (inserts or updates) details including:
     - `noc_and_line_and_servicecode`, `operator_noc`, `license`, `line_name`, `service_name` (from journey pattern description), and array of admin areas.
   - Uses `ON CONFLICT` to merge admin areas and update other fields as needed.

7. **Analyze `service_details` Table**
   - Runs `ANALYSE` on the table to update statistics.

8. **Refresh Materialized View `expected_services`**
   - Refreshes the materialized view to ensure it reflects the latest data.

9. **Delete and Insert `expected_operators`**
   - Deletes all records in `expected_operators` for the date.
   - Inserts new records by joining `expected_services` with `traveline_operators` to get operator names for the date.

10. **Analyze `expected_operators` Table**
    - Runs `ANALYSE` on the table to update statistics.

11. **Logging**
    - Logs notices at each major step for traceability and monitoring.

## Outputs
- Populates and updates the following tables and views for the specified date:
  - `expected_journeys`
  - `expected_services_by_date`
  - `service_details`
  - `expected_services` (materialized view)
  - `expected_operators`

---
This procedure is used to maintain up-to-date expected journey, service, and operator data, supporting downstream processes such as performance analysis, matching, and reporting.