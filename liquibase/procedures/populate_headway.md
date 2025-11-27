# populate_headway.sql

## Overview
This procedure calculates and updates headway (the time interval between vehicles) for journeys in the `Timetable` table for a given date. It creates a temporary table to compute actual and expected headways, then updates the main timetable with these values.

## Procedure Inputs
- **pt_date (date)**: The date for which to calculate and update headway data.

## Steps
1. **Create Temporary Headway Table**
   - Drops and recreates a temporary table `temp_timetable_headway`.
   - Calculates actual and expected headways for each journey using joins and time difference calculations.

2. **Update Timetable with Headway Data**
   - Updates the `Timetable` table with calculated headway time differences, actual headway, and expected headway for each journey.

3. **Logging**
   - Logs notices at key steps for traceability.

---
This procedure is used to support performance analysis by maintaining accurate headway data in the timetable.