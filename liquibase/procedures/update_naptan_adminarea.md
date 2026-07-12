# update_naptan_adminarea.sql

## Overview
This procedure updates the `naptan_adminarea` table with the latest admin area data from the BODS source. It inserts new records or updates existing ones as needed.

## Procedure Inputs
- **None**

## Steps
1. **Insert or Update Admin Area Data**
   - Inserts new records or updates existing ones in the `naptan_adminarea` table from the `bods.naptan_adminarea` source table.
   - Uses `ON CONFLICT` to handle updates for existing records.

2. **Logging**
   - Logs notices at key steps for traceability.

---
This procedure is used to keep the admin area data up to date in the NaPTAN system.