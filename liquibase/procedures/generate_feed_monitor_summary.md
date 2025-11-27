
# generate_feed_monitor_summary.sql

## Overview
This procedure generates a detailed hourly summary of feed monitoring data for all operators, including advanced outage detection, update frequency, and availability calculations. It processes data from the `feed_monitor_minute_summary` table, detects outages using window functions, aggregates statistics, and upserts results into the `feed_monitor_summary` table. The procedure is designed to support monitoring, alerting, and performance analysis for feed data ingestion.

## Procedure Inputs
- **start_point** (`timestamp with time zone`, default: start of previous hour): The timestamp used to determine the hour for which to generate the summary.

## Step-by-Step Logic

### 1. Set Hour Boundaries
- Calculates `start_hour` (truncated to the hour of `start_point`) and `end_hour` (one hour after `start_hour`).

### 2. Aggregate All Data for the Hour
- Drops and recreates a temporary table `temp_generate_feed_monitor_summary_all`.
- Aggregates data from `feed_monitor_minute_summary` for the target hour, grouped by operator and minute.
- Uses window functions to:
   - Detect outages (periods with no actual data for an operator).
   - Assign contiguous outage groups.
   - Calculate outage group lengths, start and end times, and flags for total outages and unavailability.
   - Compute statistics: expected, actual, minutes with expected, live locations, etc.

### 3. Outage Length Calculation
- Creates a CTE (`outage_lengths`) to calculate the length and boundaries of each outage group for each operator.
- Determines if an outage is a total outage (entire hour) or partial, and whether the operator is currently unavailable.

### 4. Update Frequency and Availability (Last 24h)
- Drops and recreates `temp_generate_feed_monitor_summary_update_frequencies`.
- Calculates, for each operator, the update frequency (average updates per minute) and availability (proportion of minutes with actual data) over the last 24 hours.
- Only includes operators present in the current hour.

### 5. Outage Summary by Operator
- Drops and recreates `temp_generate_feed_monitor_summary_by_noc`.
- For each operator, determines:
   - The most recent outage group and its properties (length, start, end, total outage, unavailability).
   - Joins with update frequency and availability from the previous step.
   - Joins with the previous summary record for comparison (previous outage, previous unavailability, etc.).

### 6. Prepare Upsert Values
- Drops and recreates `temp_generate_feed_monitor_new_values`.
- For each operator, determines the values to upsert:
   - `update_frequency`: Calculated or null if no data.
   - `availability`: Proportion of available minutes (0 if null).
   - `unavailable_since`: Timestamp when the operator became unavailable (logic considers total outages and previous state).
   - `last_outage`: Timestamp of the last outage (current or previous, as appropriate).

### 7. Upsert into Summary Table
- Upserts (inserts or updates) the calculated values into `feed_monitor_summary` for each operator using `ON CONFLICT (operator_noc)`.
- Updates the following fields:
   - `update_frequency`
   - `availability`
   - `unavailable_since`
   - `last_outage`

### 8. Logging and Ownership
- Logs notices at key steps for traceability.
- Sets the procedure owner to `abods_proxy_rw`.

## Outputs
- The `feed_monitor_summary` table is updated for each operator with the latest hourly statistics:
   - `operator_noc`: Operator identifier
   - `update_frequency`: Average updates per minute (last 24h)
   - `availability`: Proportion of available minutes (last 24h)
   - `unavailable_since`: Timestamp when the operator became unavailable
   - `last_outage`: Timestamp of the last outage

## Notes
- The procedure uses several temporary tables and CTEs for intermediate calculations.
- Outage detection is based on configurable thresholds (e.g., `consecutive_missing`).
- The logic ensures that both new and existing operators are handled, and previous state is considered for continuity.

---
This procedure is critical for monitoring feed health, detecting outages, and supporting alerting and reporting on operator data availability.