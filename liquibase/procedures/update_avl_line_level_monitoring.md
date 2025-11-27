# update_avl_line_level_monitoring.sql

## Overview
This procedure updates the `avl_line_level_monitoring` table with the latest recorded AVL (Automatic Vehicle Location) data for each operator and line for a given date. It inserts or updates the last recorded time for each operator and line combination.

## Procedure Inputs
- **partition_date (date, default: yesterday)**: The date for which to update AVL line-level monitoring data.

## Steps
1. **Insert or Update Monitoring Data**
   - Aggregates the latest `recorded_at_time` for each operator and line from the `SiriVMPositions` table for the specified date.
   - Inserts new records or updates existing ones in the `avl_line_level_monitoring` table.

2. **Logging**
   - Logs notices at key steps for traceability.

---
This procedure is used to maintain up-to-date AVL monitoring data at the line level.