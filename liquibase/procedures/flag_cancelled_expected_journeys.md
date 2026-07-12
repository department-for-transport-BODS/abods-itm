# flag_cancelled_expected_journeys.sql

## Overview
This procedure flags cancelled journeys in the `expected_journeys` table for a given partition date. It first resets all cancellation flags for the date, then sets the flag for journeys that are identified as cancelled based on the latest situation data from the `siri_sx_situations` table.

## Procedure Inputs
- **partition_date (date)**: The date for which expected journeys should be flagged as cancelled.

## Steps
1. **Reset Cancellation Flags**
   - Sets `is_cancelled` to `FALSE` for all journeys in `expected_journeys` for the given date.

2. **Flag Cancelled Journeys**
   - Identifies the latest situation for each journey (by `producer_ref`, `operator_noc`, `line_name`, `journey_code`, `direction`) for the date from `siri_sx_situations`.
   - Sets `is_cancelled` to `TRUE` for journeys where the latest situation's `condition` is not `'normalService'`.

3. **Logging**
   - Logs notices at the start and end of the process for traceability.

---
This procedure is used to keep the `expected_journeys` table up to date with the latest cancellation information for each journey.