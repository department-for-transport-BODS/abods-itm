SELECT cron.schedule(
               'Update headway & SiriVMposition id',
               '00 01 * * *', -- at 01:00
               $$CALL public.populate_headway(CURRENT_DATE - 2);CALL public.populate_headway(CURRENT_DATE - 1);CALL public.incomplete_data_load(CURRENT_DATE - 2);CALL public.incomplete_data_load(CURRENT_DATE - 1);$$
       );

SELECT cron.schedule(
               'summary_by_stop',
               '00 02 * * *', -- at 02:00
               $$CALL public.summary_by_stops(CURRENT_DATE - 2);CALL public.summary_by_stops(CURRENT_DATE - 1);$$
       );

SELECT cron.schedule(
               'summary_by_services',
               '40 02 * * *', -- at 02:40
               $$CALL public.summary_by_services(CURRENT_DATE - 2);CALL public.summary_by_services(CURRENT_DATE - 1);$$
       );

SELECT cron.schedule(
               'summary_by_operators',
               '00 03 * * *', -- at 03:00am
               $$CALL public.summary_by_operators(CURRENT_DATE - 2);CALL public.summary_by_operators(CURRENT_DATE - 1);$$
       );

SELECT cron.schedule(
               'frequent_summary_services',
               '00 02 * * *', -- at 02:00
               $$CALL public.frequent_summary_services();$$
       );

SELECT cron.schedule(
               'Refresh create_timetable_threshold_summary',
               '00 03 * * *', -- at 03:00
               $$CALL public.create_timetable_threshold_summary(CURRENT_DATE - 2);CALL public.create_timetable_threshold_summary(CURRENT_DATE - 1);$$
       );

SELECT cron.schedule(
               'update feed stats',
               '05 * * * *', -- every 5 mins
               $$call public.generate_feed_monitoring_data();call public.generate_feed_monitor_summary();$$
       );

SELECT cron.schedule(
               'partman.run_maintenance_proc',
               '15 23 * * *', -- at 23:15
               $$CALL partman.run_maintenance_proc();$$
       );

SELECT cron.schedule(
               'update feed hourly stats',
               '15 01 * * *', -- at 01:15
               $$call public.generate_feed_monitoring_daily_summary();$$
       );

SELECT cron.schedule(
               'update avl line level monitoring',
               '25 01 * * *', -- at 01:25
               $$call public.update_avl_line_level_monitoring();$$
       );

SELECT cron.schedule(
               'Update Admin Area Shapes',
               '05 02 01 * *', -- at 02:05 on the first day of the month
               $$CALL public.update_naptan_adminarea_shape();$$
       );

SELECT cron.schedule(
               'update_performance_statistics_v4',
               '10 03 * * *', -- at 03:10
               $$CALL public.update_performance_statistics_v4();$$
       );

SELECT cron.schedule(
               'Refresh noc_adminarea materialized view',
               '05 03 * * *', -- at 03:05
               $$refresh MATERIALIZED VIEW public.noc_adminarea;$$
       );

SELECT cron.schedule(
               'partman.partition_data_proc',
               '00 22 * * *', -- at 22:00
               $$CALL partman.partition_data_proc('public.SiriVMPositions');$$
       );

SELECT cron.schedule(
               'update ui lta',
               '00 02 * * *', -- at 02:00
               $$CALL update_ui_lta();$$
       );

SELECT cron.schedule(
               'generate timetable',
               CASE
                   WHEN SPLIT_PART(aurora_db_instance_identifier(), '-', 2) = 'sandbox' THEN '35 19 * * *' -- at 19:35
                   WHEN SPLIT_PART(aurora_db_instance_identifier(), '-', 2) = 'uat' THEN '05 19 * * *' -- at 19:05
                   ELSE '05 18 * * *' -- at 18:05
                   END,
               $$CALL update_all_transmodel_tables();CALL update_all_naptan_tables();CALL generate_timetable(CURRENT_DATE + 1);CALL generate_expected_tables(CURRENT_DATE + 1);CALL update_distinct_routes(CURRENT_DATE + 1);$$
       );

SELECT cron.schedule(
               'generate_license_lines_with_dq_issues',
               '00 05 * * SUN', -- sundays at 05:00
               $$CALL generate_license_lines_with_dq_issues(CURRENT_DATE);$$
       );
