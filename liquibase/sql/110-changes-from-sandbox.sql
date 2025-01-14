ALTER TABLE public.transmodel_servicepatternstop DROP COLUMN IF EXISTS auto_sequence_number;

ALTER TABLE public."Timetable" DROP COLUMN IF EXISTS recorded_at_time_utc;

ALTER TABLE public.timetable_summary_operator_t ALTER COLUMN operator_noc SET NOT NULL;
ALTER TABLE public.timetable_summary_operator_t ALTER COLUMN date_of_journey SET NOT NULL;
ALTER TABLE public.timetable_summary_operator_t ALTER COLUMN departure_hour SET NOT NULL;
ALTER TABLE public.timetable_summary_operator_t ALTER COLUMN departure_hour_only SET NOT NULL;
ALTER TABLE public.timetable_summary_operator_t ALTER COLUMN day_of_week SET NOT NULL;
ALTER TABLE public.timetable_summary_operator_t ALTER COLUMN is_timing_point SET NOT NULL;
ALTER TABLE public.timetable_summary_operator_t ALTER COLUMN max_early SET NOT NULL;
ALTER TABLE public.timetable_summary_operator_t ALTER COLUMN max_late SET NOT NULL;
ALTER TABLE public.timetable_summary_operator_t ALTER COLUMN avg_time_difference SET NOT NULL;
ALTER TABLE public.timetable_summary_operator_t ALTER COLUMN admin_areas SET NOT NULL;

ALTER TABLE public.timetable_summary_service_tz ALTER COLUMN estimated SET NOT NULL;

ALTER TABLE public.timetable_summary_stops_tz ALTER COLUMN estimated SET NOT NULL;
ALTER TABLE public.timetable_summary_stops_tz ALTER COLUMN line_name SET NOT NULL;

ALTER TABLE public.feed_monitor_summary DROP CONSTRAINT IF EXISTS feed_monitor_summary_pk;

ALTER TABLE public.timetable_summary_operator ADD COLUMN estimated boolean;
ALTER TABLE public.timetable_summary_service ADD COLUMN estimated boolean;
