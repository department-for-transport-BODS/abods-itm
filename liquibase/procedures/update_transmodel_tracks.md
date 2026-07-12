# update_transmodel_tracks.sql

## Overview
This procedure updates the `transmodel_tracks` table with the latest track records from the BODS source. It inserts new or updates existing records, and removes any records not present in the source.

## Procedure Inputs
- **None**

## Steps
1. **Insert or Update Track Records**
   - Inserts new or updates existing records in the `transmodel_tracks` table from the `bods.transmodel_tracks` source table.
   - Uses `ON CONFLICT` to update geometry and distance for existing records.

2. **Delete Obsolete Records**
   - Deletes records from `transmodel_tracks` that are no longer present in the source table.

3. **Logging**
   - Logs notices at key steps for traceability.

---
This procedure is used to keep the track records up to date in the system.