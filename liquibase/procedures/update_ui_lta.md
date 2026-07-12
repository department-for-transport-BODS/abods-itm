# update_ui_lta.sql

## Overview
This procedure updates the `ui_lta` table with the latest LTA (Local Transport Authority) records from the BODS source. It truncates the table and inserts new records.

## Procedure Inputs
- **None**

## Steps

1. **Truncate Table**
   - Removes all records from `ui_lta` to prepare for fresh data.

2. **Insert New LTA Records**
   - Copies the latest records from `bods.ui_lta` into `ui_lta`.

3. **Logging**
   - Logs notices before and after key actions for traceability.

---
This procedure is used to keep the LTA records up to date in the system.