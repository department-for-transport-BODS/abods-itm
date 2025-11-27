# historic_avl_export.sql

## Overview
This procedure exports AVL (Automatic Vehicle Location) data from the `SiriVMPositions` table for a given date to an S3 bucket in CSV format. It uses the AWS S3 extension for PostgreSQL to perform the export.

## Procedure Inputs
- **partition_date (date)**: The date for which to export AVL data.

## Steps
1. **Format Date String**
   - Converts `partition_date` to a string in 'YYYY-MM-DD' format for use in file naming and queries.

2. **Export Data to S3**
   - Uses the `aws_s3.query_export_to_s3` function to export selected columns from `SiriVMPositions` for the specified date.
   - The export is written to a path in the S3 bucket, organized by year and month, and named with the date.
   - The export is performed in CSV format.

3. **Logging**
   - Logs notices before and after the export for traceability.

---
This procedure is used to automate the export of historic AVL data for archiving or downstream processing.