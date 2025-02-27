SELECT cron.schedule(
               'Update headway & SiriVMposition id',
               '00 01 * * *',
               $$CALL public.populate_headway(CURRENT_DATE - '2 day'::interval);CALL public.populate_headway(CURRENT_DATE - '1 day'::interval);CALL public.incomplete_data_load(CURRENT_DATE - '2 day'::interval);CALL public.incomplete_data_load(CURRENT_DATE - '1 day'::interval);$$
       );

SELECT cron.schedule(
               'summary_by_stop',
               '0 2 * * *',
               $$CALL public.summary_by_stops(CURRENT_DATE - '2 day'::interval);CALL public.summary_by_stops(CURRENT_DATE - '1 day'::interval);$$
       );

SELECT cron.schedule(
               'summary_by_services',
               '20 2 * * *',
               $$CALL public.summary_by_services(CURRENT_DATE - '2 day'::interval);CALL public.summary_by_services(CURRENT_DATE - '1 day'::interval);$$
       );

SELECT cron.schedule(
               'summary_by_operators',
               '30 2 * * *',
               $$CALL public.summary_by_operators(CURRENT_DATE - '2 day'::interval);CALL public.summary_by_operators(CURRENT_DATE - '1 day'::interval);$$
       );


SELECT cron.schedule(
               'frequent_summary_services',
               '0 2 * * *',
               $$CALL public.frequent_summary_services();$$
       );

SELECT cron.schedule(
               'Refresh create_timetable_threshold_summary',
               '30 02 * * *',
               $$CALL public.create_timetable_threshold_summary(CURRENT_DATE - '2 day'::interval);CALL public.create_timetable_threshold_summary(CURRENT_DATE - '1 day'::interval);$$
       );
