# ABODS ITM Sandbox

Repository relating to the Analyse Bus Registration Data service that is offered by DfT (Department for Transport).
Specifically this contains code relating to the Backend ITM (Integrated Data Management) Services.

## Category

Supporting application backend microservices.

## Tech Stack

- Liquibase
- Python
- AWS SAM (Serverless Application Model)

## Ingestion Pipelines

```mermaid

flowchart LR
    A[(1. Prod S3 bucket
    SiriVM zips)] --> B((SQS Queue))
    B --> |abods-sandbox-sirivm-ingestion-queue| C(2. S3 Ingestion
    gzip csv)
    C --> D[(S3)]
    D --> E((SQS Queue))
    E -->|OTP Queue| F(5. OTP Matching)
    E -->|Process Queue| G(3. DB ingestion)
    H(4. Timetable S3 Ingestion) --> I[(S3)]
    I --> |OTP Queue|F

```

### 1. Prod S3 Bucket SiriVM zips

The SiriVM AVL gzip files obtained from BODS.

When the S3 bucket's got the latest AVL data every 10 seconds, it sends a message to abods-sandbox-sirivm-ingestion-queue which will be received by step-2 S3 Ingestion and initiates the ingestion process

### 2. S3 Ingestion

S3 Ingestion's lambda handler function

- receives SQS message from abods-sandbox-sirivm-ingestion-queue
- obtains AVL data gzip file from s3 bucket
- parses and extracts AVL data in xml format and write it to csv format and into a gzip file
- uploads converted AVL data in gzip file to s3 bucket
- sends message to process queue trigger 3. DB Ingestion
- sends message to otp queue to trigger 5. OTP Matching function

### 3. DB Ingestion

DB Ingestion's lambda handler function

- receives SQS message from process queue
- connects to database and retrieves the AVL batch table
- truncates staging avl positions table
- rewrites staging table with avl data extracted from S3 ingestion
- updates AVL batch table with data from staging table

### 4. Timetable S3 Ingestion

Timetable data is updated every 30 minutes.

Timetable S3 Ingestion's lambda handler function

- connects to database and extract data from specific columns for OTP matching from timetable
- writes the extracted data into json format and loads it to S3 bucket
- sends message to otp queue to trigger 5. OTP Matching function

### 5. OTP Matching

OTP Matching's lambda handler function

- receives SQS message from otp queue
- retrieves and read AVL data in csv format from s3 bucket
- matches position data to the timetable data
- calculates the distance between bus position and the stop and get the bus actual departure time to analyse bus on time performance
- connects to the database
- updates the timetable with the bus punctuality
- writes AVL last positions data to s3 bucket

#### Historic matching v1

If a change is made to the matching process, and past journeys must be reprocessed, the following manual process can be used to re-process those journeys.

1. Timetable shredding

   The code in `injestion_pipelines/sirivm_timetable_s3_generation_function` is used to produce S3 extracts of the data in the `Timetable` table of the PostgreSQL database. 
   We can produce a full day's extracts by sending a test event to the deployed lambda function `abods-$ENVIRONMENT-sirivm-timetable-s3-generation-function`.
   We should not need to repeat shredding unless the format of the extract changes, or the source timetable data is updated.  
   For example, to trigger shredding for the 15th October 2024:
   ```json
   {
     "backfill_start_date": "2024-10-15",
     "backfill_end_date": "2024-10-15"
   }
   ```
2. Historic matching

   After the shredding process is complete we can start historic matching.
   The code in `injestion_pipelines/sirivm_s3_ingestion_function` co-ordinates the matching process for a full day's data, and adds events to a queue that is read by one of ten historic matching lambdas. 
   To trigger the process, send a test event to the deployed lambda at `abods-$ENVIRONMENT-sirivm-backfill-ingestion-function`.
   For example, to trigger matching for the 15th October 2024:
   ```json
   {
     "backfill_start_date": "2024-10-15",
     "backfill_end_date": "2024-10-15",
     "concurrency": "1"
   }
   ```

#### Historic matching v2

This historic matching method uses both avl and timetable data in parquet format for re-processing.

1. Exporting timetable data

   The function `public.export_timetable_exporter` is for exporting timetable data from database to s3 bucket in csv format.

   Below is the current schema being exported.

   | Timetable |
   | ----------------------- |
   | group_id                                       |
   | stop_index                                     |
   | stop_latitude                                  |
   | stop_longitude                                 |
   | expected_departure_time                        |
   | timetable_id                                   |
   | date_of_journey                                |
   | direction                                      |
   | operator_noc                                   |

   For example, to export timetable data for the 4th December 2024: 
   
   ```SQL
   CALL public.export_timetable_exporter('2024-12-04');
   ```
   
   **It is only available in sandbox environment currently.


2. Exporting AVL data

   To export the AVL data, we can use the following code to generate the dates in SQL code that we want to re-process and execute the output SQL scripts in database.


   ```Python
   from datetime import datetime, timedelta

   dates = [
          datetime(2024, 11, 7) - timedelta(days=x)
      for x in range(15)
   ]

   for date in dates:
       print(f"""SELECT * from aws_s3.query_export_to_s3(
        'select '
        'siri_vm_positions_id, operator_ref, line_name, journey_ref, direction_ref, date_of_journey, latitude, longitude, vehicle_ref, batch_id, recorded_at_time, response_time_stamp, load_time_stamp,  '
        'lower(operator_ref || ''|'' || line_name || ''|'' || journey_ref || ''|'' || date_of_journey) as group_id, origin_ref, destination_ref, departure_time '
        'from public."SiriVMPositions" '
        'where date_of_journey = cast(''{date.year}-{date.month:02}-{date.day:02}'' as date) '
        'order by recorded_at_time, operator_ref '
        , aws_commons.create_s3_uri('abods-sandbox-exporter-bucket', 'historic/csv/siri/YYYY={date.year}/MM={date.month:02}/siri_vm_{date.year}{date.month:02}{date.day:02}.csv', 'eu-west-2')
        , options :='DELIMITER E'','', FORMAT csv, encoding ''utf-8'' '
        );
       """)
   ```

3. Converting data to parquet

   To convert the timetable and avl data from csv to parquet in s3, we can use `convert2parquet` lambda function. The code is in `injestion_pipelines/convert_to_parquet_function`. 3 parameters are passed in in order to trigger the function. First, the date we want to convert the data. Second, if the data consists of multiple parts. Some avl data consists of 2 parts. If there're 2 parts, we can set `part_2` to `true`, otherwise `false`. If we are converting timetable data, set `is_timetable` to `true`.

   To trigger the process, send a test event to the deployed lambda at `abods-$ENVIRONMENT-convert2parquet`.
   For example, to convert avl data with multiple parts for 31st October 2024:
   ```json
    {
      "process_date": "2024-10-31",
      "part_2": true,
      "is_timetable": false
    }
   ```
   to convert timetable data for 31st October 2024:
   ```json
    {
      "process_date": "2024-10-31",
      "part_2": false,
      "is_timetable": true
    }
   ```