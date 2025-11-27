# incomplete_data_load.sql

## Overview
This procedure identifies and processes incomplete journey data in the `Timetable` table for a given date. It creates temporary tables to track stops without operator NOCs or journey codes, and performs further analysis to support data quality and completeness.

## Procedure Inputs
- **partition_date (date, default: yesterday)**: The date for which to process incomplete journey data.

## Steps
1. **Create Temporary Table for Stops Without Operator NOCs**
   - Identifies timetable records for the date where the expected departure time is in the past, actual departure time is missing, and no matching operator NOC is found in `SiriVMPositions`.
   - Stores results in `incomplete_data_tmp_stops_without_operator_nocs`.

2. **Create Temporary Table for Stops Without Journey Codes**
   - Identifies timetable records for the date where the expected departure time is in the past, actual departure time is missing, and no matching journey code is found in `SiriVMPositions`.
   - Stores results in `incomplete_data_tmp_stops_without_journey_codes`.

3. **Further Analysis and Processing**
   - (The procedure contains additional steps to analyze and process incomplete data, supporting data quality and completeness.)

4. **Logging**
   - Logs notices at key steps for traceability.

---
This procedure is used to support data quality by identifying and processing incomplete journey data in the timetable.