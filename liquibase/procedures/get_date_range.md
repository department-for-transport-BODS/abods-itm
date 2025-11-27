# get_date_range.sql

## Overview
This procedure calculates a date range (start and end dates) based on a specified period type, such as 'last_7_days', 'last_28_days', 'month_to_date', or 'last_month'. It is used to standardize date range selection for reporting and analysis.

## Procedure Inputs
- **period_type (character varying)**: The type of period for which to calculate the date range. Supported values include 'last_7_days', 'last_28_days', 'month_to_date', and 'last_month'.
- **OUT start_date (date)**: The calculated start date for the period.
- **OUT end_date (date)**: The calculated end date for the period.

## Steps
1. **Set End Date**
   - Sets `end_date` to yesterday (current date minus one day).

2. **Determine Start Date Based on Period Type**
   - For 'last_7_days': Sets `start_date` to 6 days before `end_date`.
   - For 'last_28_days': Sets `start_date` to 27 days before `end_date`.
   - For 'month_to_date': Sets `start_date` to the first day of the current month.
   - For 'last_month': Sets `start_date` to the first day of the previous month and `end_date` to the last day of the previous month.
   - For any other value: Sets both `start_date` and `end_date` to NULL.

3. **Logging**
   - Logs notices for traceability.

---
This procedure is used to provide standardized date ranges for analytics and reporting.