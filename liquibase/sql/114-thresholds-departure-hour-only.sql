ALTER TABLE public.timetable_threshold_summary
    ADD COLUMN IF NOT EXISTS departure_hour_only time with time zone;
