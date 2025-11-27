# drop_sirivm_partition_by_date.sql# Procedure: drop_sirivm_partition_by_date# Procedure: drop_sirivm_partition_by_date



## Overview

This procedure drops a specific partition of the `SiriVMPositions` table for a given date, but only if the date is older than six months. It is used for data retention and cleanup, ensuring that only old partitions are removed.

## Overview## Overview

## Procedure Inputs

- **p_date (date, default: six months ago)**: The date for which the partition should be dropped. Defaults to six months ago if not specified.This procedure drops a single partition of the `SiriVMPositions` table for a specified date, but only if the date is older than six months from the current date. It is designed to:This procedure drops a single partition of the `SiriVMPositions` table for a specified date, but only if the date is older than six months from the current date. It is designed to:



## Steps- Validate that the requested date is not newer than six months ago.- Validate that the requested date is not newer than six months ago.

1. **Validate Date**

   - Checks that `p_date` is not more recent than six months ago.- Attempt to drop the partition table for the specified date.- Attempt to drop the partition table for the specified date.

   - If the date is too recent, raises an exception and aborts.

- Log the outcome, including handling the case where the partition does not exist.- Log the outcome, including handling the case where the partition does not exist.

2. **Attempt to Drop Partition**

   - Constructs the partition table name for the given date.

   - Attempts to drop the partition table using dynamic SQL.

   - Logs a notice if the partition is successfully dropped.## Inputs## Inputs

   - If the partition does not exist, logs a notice and skips.

   - If another error occurs, raises an exception with details.- `p_date` (date, default: six months ago): The date for which the partition should be dropped. Defaults to six months before the current date if not provided.- `p_date` (date, default: six months ago): The date for which the partition should be dropped. Defaults to six months before the current date if not provided.



---

This procedure is typically used as part of a data retention policy to remove old partitions from the `SiriVMPositions` table.
## Steps## Steps

1. **Calculate Partition Name and Six Months Ago**1. **Calculate Partition Name and Six Months Ago**

   - Constructs the partition table name as `SiriVMPositions_pYYYY_MM_DD` for the given date.   - Constructs the partition table name as `SiriVMPositions_pYYYY_MM_DD` for the given date.

   - Sets `v_six_months_ago` to the date six months before the current date.   - Sets `v_six_months_ago` to the date six months before the current date.



2. **Validate Date**2. **Validate Date**

   - Checks if `p_date` is more recent than six months ago. If so, raises an exception and aborts.   - Checks if `p_date` is more recent than six months ago. If so, raises an exception and aborts.



3. **Attempt to Drop Partition**3. **Attempt to Drop Partition**

   - Tries to drop the partition table for the specified date using dynamic SQL.   - Tries to drop the partition table for the specified date using dynamic SQL.

   - Logs a notice if the partition is successfully dropped.   - Logs a notice if the partition is successfully dropped.

   - If the partition does not exist, logs a notice and skips.   - If the partition does not exist, logs a notice and skips.

   - If another error occurs, raises an exception with the error message.   - If another error occurs, raises an exception with the error message.



## Notes## Notes

- The procedure uses exception handling to manage missing partitions and other errors.- The procedure uses exception handling to manage missing partitions and other errors.

- The default value for `p_date` ensures that, if called without arguments, it targets the partition for six months ago.- The default value for `p_date` ensures that, if called without arguments, it targets the partition for six months ago.

