# load_avl_tables_historic.sql

## Overview
This procedure loads historic AVL (Automatic Vehicle Location) data from a staging table into a partitioned `SiriVMPositions` table for a given date. It creates the partition if it does not exist, inserts the data, and then truncates the staging table.

## Procedure Inputs
- **pt_date (date)**: The date for which to load AVL data.

## Steps
1. **Set Partition Date and Table Name**
   - Sets `partition_date` to the input date and constructs the partition table name as `SiriVMPositions_pYYYY_MM_DD`.

2. **Create Partition Table if Not Exists**
   - Creates a partition for the specified date if it does not already exist.
   - Sets the table owner to `abods_rw`.

3. **Insert Data from Staging Table**
   - Inserts data from `staging_avl_positions_historic` into the partitioned table, transforming and formatting fields as needed.
   - Uses `ON CONFLICT DO NOTHING` to avoid duplicate inserts.

4. **Truncate Staging Table**
   - Truncates the staging table after the data has been loaded.

---
This procedure is used to efficiently load and partition historic AVL data for downstream analysis and reporting.