select cron.schedule('Second run adding headway and incomplete reasonings to timetable to capture departure day shift', '0 17 * * *',  $$call public.populate_headway(now()::date - 1);call public.incomplete_data_load(now()::date - 1); $$);


select cron.schedule('Second run create_timetable_threshold_summary to capture departure day shift', '30 17 * * *',  $$call create_timetable_threshold_summary(now()::date - 1); $$);
