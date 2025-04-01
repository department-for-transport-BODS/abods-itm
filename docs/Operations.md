# Operations Guide

## Logging

Although logging have not been updated in all services yet, the project is set up to use structured logging.
The OTP matching code makes extensive use of this using [Powertools for AWS Lambda](https://docs.powertools.aws.dev/lambda/python/latest/core/logger/#standard-structured-keys)

You can use AWS CloudWatch Logs Insights to get a view into the current behaviour of the matching process.

Here are some examples of useful queries.
A link to the query is provided for convenience, but you might need to change the target log group if you are not looking at the sandbox environment:

### Live matching queries

[Number of OTP matches produced per minute](https://eu-west-2.console.aws.amazon.com/cloudwatch/home?region=eu-west-2#logsV2:logs-insights$3FqueryDetail$3D~(end~0~start~-7200~timeType~'RELATIVE~tz~'UTC~unit~'seconds~editorString~'filter*20message*20*3d*20*27Processed*20batch*27*0a*7c*20stats*20sum*28new_matches*29*20by*20bin*281m*29~queryId~'4aedef95-adc4-4d88-b9b7-7da8bfdf5d9f~source~(~'*2faws*2flambda*2fabods-sandbox-sirivm-otp-matching-function)~lang~'CWLI)$26tab$3Dvisualization$26chartType$3Dline)
```
filter message = 'Processed batch'
| stats sum(new_matches) by bin(1m)
```

[Average time taken to update the database each minute](https://eu-west-2.console.aws.amazon.com/cloudwatch/home?region=eu-west-2#logsV2:logs-insights$3FqueryDetail$3D~(end~0~start~-7200~timeType~'RELATIVE~tz~'UTC~unit~'seconds~editorString~'filter*20message*20*3d*20*27Finished*20live_update_success*28*29*27*0a*7c*20stats*20avg*28time_in_ms*29*20by*20bin*281m*29~queryId~'4aedef95-adc4-4d88-b9b7-7da8bfdf5d9f~source~(~'*2faws*2flambda*2fabods-sandbox-sirivm-otp-matching-function)~lang~'CWLI)$26tab$3Dvisualization$26chartType$3Dline)
```
filter message = 'Finished live_update_success()'
| stats avg(time_in_ms) by bin(1m)
```

### Historic matching queries

> [!NOTE]
> These queries need to have the `process_date` value updated

[Operators remaining in queue](https://eu-west-2.console.aws.amazon.com/cloudwatch/home?region=eu-west-2#logsV2:logs-insights$3FqueryDetail$3D~(end~0~start~-3600~timeType~'RELATIVE~tz~'UTC~unit~'seconds~editorString~'filter*20message*20*3d*20*27Processing*20operator*27*0a*7c*20filter*20PROCESS_DATE*20*3d*20*27process_date*27*0a*7c*20stats*20min*28estimated_remaining_groups*29~queryId~'24d2db57-c6b9-4487-b6bf-0c4e178587bc~source~(~'*2faws*2fecs*2fabods-sandbox)~lang~'CWLI))
```
filter message = 'Processing operator'
| filter PROCESS_DATE = 'process_date'
| stats min(estimated_remaining_groups)
```

[Rough matching stats](https://eu-west-2.console.aws.amazon.com/cloudwatch/home?region=eu-west-2#logsV2:logs-insights$3FqueryDetail$3D~(end~0~start~-3600~timeType~'RELATIVE~tz~'UTC~unit~'seconds~editorString~'fields*20total_routes*2c*20routes_processed*2c*20total_stops*2c*20total_matches*2c*20operator_ref*0a*7c*20filter*20message*20*3d*20*27Processed*20operator*20data*27*0a*7c*20filter*20PROCESS_DATE*20*3d*20*27process_date*27~queryId~'24d2db57-c6b9-4487-b6bf-0c4e178587bc~source~(~'*2faws*2fecs*2fabods-sandbox)~lang~'CWLI))
```
fields total_routes, routes_processed, total_stops, total_matches, operator_ref
| filter message = 'Processed operator data'
| filter PROCESS_DATE = 'process_date'
```

## Database issues

Usually when we see issues with the database, there is a long-running query a denial of service to other workloads.
Try connecting to the database and running this query:
```sql
SELECT
  pid,
  now() - pg_stat_activity.query_start AS duration,
  query,
  state
FROM pg_stat_activity
WHERE (now() - pg_stat_activity.query_start) > interval '5 minutes'
ORDER by state, pg_stat_activity.query_start;
```

If there are lots, of results in active state, then the one with the earliest start time is likely the cause.

Try to determine what is running that query, and if it is safe to do so, consider cancelling it like this:
```sql
SELECT pg_cancel_backend(__pid__);
```

Very occasionally it can be necessary to reboot the database instance.
This can be done from the AWS UI.
It is reasonable to do this in an emergency, but to be on the safe side, you might consider this process: 
1. Disable the lambda trigger on the s3 ingestion queue
2. Wait for the queues other queues to be empty
3. Reboot the database
4. Enable the lambda trigger (a re-deployment through GitHub actions might help here)
