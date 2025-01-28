ALTER TABLE public."Timetable"
    ADD COLUMN IF NOT EXISTS incomplete_reason int;

ALTER TABLE public."timetable_summary_stops_tz"
    ADD COLUMN IF NOT EXISTS incomplete_reason int;
 
ALTER TABLE public."timetable_summary_service_tz"
    ADD COLUMN IF NOT EXISTS incomplete_reason int;

ALTER TABLE public."timetable_summary_operator_t"
    ADD COLUMN IF NOT EXISTS incomplete_reason int;