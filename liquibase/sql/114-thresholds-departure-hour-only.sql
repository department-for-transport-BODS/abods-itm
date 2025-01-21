ALTER TABLE abods.public.timetable_threshold_summary
    ADD COLUMN IF NOT EXISTS departure_hour_only time with time zone NOT NULL default date_of_journey::date || ' ' || departure_hour::time::text;
