# populate_avl_recorded_expected_journeys.sql

## Overview
This procedure updates the `expected_journeys` table to indicate whether AVL (Automatic Vehicle Location) data was recorded for each journey on a given date. It sets all journeys as recorded, then marks as not recorded those with incomplete reasons in the timetable.

## Procedure Inputs
- **partition_date (date, default: yesterday)**: The date for which to update AVL recorded status.

## Steps
1. **Set All Journeys as Recorded**
   - Sets `avl_recorded` to `TRUE` for all journeys in `expected_journeys` for the date.

2. **Mark Journeys as Not Recorded**
   - Sets `avl_recorded` to `FALSE` for journeys where the corresponding timetable entry has an incomplete reason (values 1, 2, or 3).

3. **Logging**
   - Logs notices at the start and end of the process for traceability.

---
This procedure is used to maintain accurate AVL recording status for expected journeys.