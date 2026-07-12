# update_transmodel_servicepatterndistance.sql

## Overview
This procedure updates the `transmodel_servicepatterndistance` table with the latest service pattern distance records from the BODS source. It inserts new records as needed, avoiding duplicates.

## Procedure Inputs
- **None**

## Steps
1. **Insert New Service Pattern Distance Records**
   - Inserts new records into the `transmodel_servicepatterndistance` table from the `bods.transmodel_servicepatterndistance` source table.
   - Uses `ON CONFLICT DO NOTHING` to avoid inserting duplicates.

2. **Logging**
   - Logs notices at key steps for traceability.

---
This procedure is used to keep the service pattern distance records up to date in the system.