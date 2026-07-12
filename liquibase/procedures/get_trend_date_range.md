# get_trend_date_range.sql

## Overview
This procedure calculates a date range (start and end dates) for trend analysis, based on a specified period type. It is similar to `get_date_range` but offsets the range to the previous period for trend comparison.

## Procedure Inputs
- **period_type (character varying)**: The type of period for which to calculate the trend date range. Supported values include 'last_7_days', 'last_28_days', 'month_to_date', and 'last_month'.
- **OUT start_date (date)**: The calculated start date for the trend period.
- **OUT end_date (date)**: The calculated end date for the trend period.

## Steps
1. **Set End Date**
   - Sets `end_date` to yesterday (current date minus one day).

2. **Determine Trend Date Range Based on Period Type**
   - For 'last_7_days': Sets range to the 7 days prior to the last 7 days.
   - For 'last_28_days': Sets range to the 28 days prior to the last 28 days.
   - For 'month_to_date': Sets range to the previous month's equivalent period.
   - For 'last_month': Sets range to the month before last.
   - For any other value: Sets both `start_date` and `end_date` to NULL.

3. **Logging**
   - Logs notices for traceability.

---
This procedure is used to provide standardized trend date ranges for analytics and reporting.