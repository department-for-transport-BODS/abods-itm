# update_transmodel_vehiclejourney.sql

## Overview
This procedure updates the `transmodel_vehiclejourney` table with the latest vehicle journey records from the BODS source. It inserts new records as needed, avoiding duplicates.

## Procedure Inputs
- **None**

## Steps
1. **Insert New Vehicle Journey Records**
   - Inserts new records into the `transmodel_vehiclejourney` table from the `bods.transmodel_vehiclejourney` source table.
   - Uses `ON CONFLICT DO NOTHING` to avoid inserting duplicates.

2. **Logging**
   - Logs notices at key steps for traceability.

---
This procedure is used to keep the vehicle journey records up to date in the system.