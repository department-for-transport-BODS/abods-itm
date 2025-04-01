# Data

The database is an AWS Aurora Serverless v2 Postgres cluster with an RDS proxy.

Liquibase is used for migrations.
- One off migrations (schema changes) are stored in [sql](../liquibase/sql). Don't change these, add a new one.
- Procedures are stored in [procedures](../liquibase/procedures) and can be edited
- Functions are stored in [functions](../liquibase/functions) and can be edited
- Scheduled jobs are stored in [cron.sql](../liquibase/cron.sql)

All new files must be added to [db.changelog.xml](../liquibase/db.changelog.xml) or else they will not be applied on deployment.

Note: no migrations are run in the sandbox environment. Changes must be manually run against the database.

## BODS data copy, and timetable generation

Every evening we copy data from the BODS database into the ABODS database, 
and run the [`generate_timetable`](../liquibase/procedures/generate_timetable.sql) procedure to generate a concrete set of timetable data specific to the next day, 
as well as a summary of the expected services.
The `generate timetable` cron job has the full list of procedures run.

## Summary generation

Every night, we run a variety of database procedures to calculate aggregate OTP stats.
We do this for the previous day, in order to have some stats ready to view in the morning 
We also do this for the day before, in order to pick up matching data that has occurred for services that continue after midnight, and after the last job run.

These procedures are run:
- [`generate_feed_monitoring_daily_summary`](../liquibase/procedures/generate_feed_monitoring_daily_summary.sql)
- [`update_avl_line_level_monitoring`](../liquibase/procedures/update_avl_line_level_monitoring.sql)
- [`populate_headway`](../liquibase/procedures/populate_headway.sql)
- [`summary_by_stops`](../liquibase/procedures/summary_by_stops.sql)
- [`summary_by_services`](../liquibase/procedures/summary_by_services.sql)
- [`summary_by_operators`](../liquibase/procedures/summary_by_operators.sql)
- [`frequent_summary_services`](../liquibase/procedures/frequent_summary_services.sql)
- [`create_timetable_threshold_summary`](../liquibase/procedures/create_timetable_threshold_summary.sql)
- [`update_performance_statistics_v4`](../liquibase/procedures/update_performance_statistics_v4.sql)

