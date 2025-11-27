# update_expected_service_distances.sql

## Overview
This procedure updates the `expected_services_by_date` table with total and AVL-recorded distances for each service, based on journey and service pattern data for a given date. It aggregates distance metrics using joins and updates the summary table.

## Procedure Inputs
- **partition_date (date, default: yesterday)**: The date for which to update expected service distances.

## Steps
1. **Aggregate Journey and Service Pattern Data**
   - Identifies journeys and joins them with expected journeys and service pattern distances.
   - Aggregates total journey counts and distances, as well as counts and distances for journeys with AVL recorded.

2. **Update Summary Table**
   - Updates the `expected_services_by_date` table with the aggregated total and AVL-recorded distances for each service and date.

3. **Logging**
   - Logs notices at key steps for traceability.

---
This procedure is used to maintain up-to-date distance metrics for expected services, supporting performance analysis and reporting.