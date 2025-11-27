# update_naptan_adminarea_shape.sql

## Overview
This procedure updates the `naptan_adminarea_shape` table with new shapes for admin areas, calculated as concave hulls of stop locations. It deletes old shapes and inserts new ones based on spatial aggregation.

## Procedure Inputs
- **None**

## Steps
1. **Delete Existing Shapes**
   - Deletes all records from the `naptan_adminarea_shape` table.

2. **Insert New Shapes**
   - Calculates new shapes for each admin area as the concave hull of all stop locations within the UK borders, excluding certain admin areas.
   - Inserts the new shapes into the `naptan_adminarea_shape` table.

3. **Logging**
   - Logs notices at key steps for traceability.

---
This procedure is used to maintain up-to-date spatial shapes for admin areas in the NaPTAN system.