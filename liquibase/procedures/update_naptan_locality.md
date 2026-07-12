# update_naptan_locality.sql

## Overview
This procedure updates the `naptan_locality` table with the latest locality data from the BODS source. It inserts new records or updates existing ones as needed.

## Procedure Inputs
- **None**

## Steps
1. **Insert or Update Locality Data**
   - Inserts new records or updates existing ones in the `naptan_locality` table from the `bods.naptan_locality` source table.
   - Uses `ON CONFLICT` to handle updates for existing records.

2. **Logging**
   - Logs notices at key steps for traceability.

---
This procedure is used to keep the locality data up to date in the NaPTAN system.