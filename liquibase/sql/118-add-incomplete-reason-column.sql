ALTER TABLE public."Timetable"
    ADD COLUMN IF NOT EXISTS incomplete_reason int;
