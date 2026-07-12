
# drop_sirivm_partitions_in_range.sql

## Overview
This procedure drops partitions of the `SiriVMPositions` table for a specified date range, but only for dates older than six months. It is used for data retention management, allowing old partitions to be removed in bulk while protecting recent data required for reporting and vehicle journey analysis.

## Procedure Inputs
- **p_start_date** (`date`): The start date of the range for which partitions should be dropped.
- **p_end_date** (`date`, optional): The end date of the range. If not provided, only the partition for `p_start_date` is dropped.

## Step-by-Step Logic

### 1. Calculate Six-Month Cutoff
- Calculates `v_six_months_ago` as the current date minus six months. This is the cutoff for which partitions are eligible for deletion.

### 2. Validate Date Range
- Checks that neither `p_start_date` nor `p_end_date` (if provided) is more recent than six months ago.
- If the range includes newer dates, raises an exception and aborts the procedure to prevent accidental deletion of recent data.

### 3. Iterate Over Date Range
- Uses a loop to iterate over each date in the range from `p_start_date` to `p_end_date` (or just `p_start_date` if `p_end_date` is not provided).
- For each date, calls the `drop_sirivm_partition_by_date` procedure to drop the corresponding partition from the `SiriVMPositions` table.

## Outputs
- Drops the partitions for all eligible dates in the specified range.
- If any date in the range is too recent, the procedure raises an exception and no partitions are dropped.

## Notes
- This procedure is typically used for automated cleanup of old data partitions to manage storage and improve performance.
- Ensures compliance with data retention policies by protecting recent data.
- Relies on the existence of the `drop_sirivm_partition_by_date` procedure to perform the actual partition drop for each date.

---
This procedure is essential for managing storage and maintaining performance by removing obsolete data while safeguarding recent records.