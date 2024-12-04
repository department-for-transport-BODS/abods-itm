ALTER TABLE public."Timetable" ADD COLUMN IF NOT EXISTS direction text;
ALTER TABLE public."Timetable" ADD COLUMN IF NOT EXISTS departure_day_shift bool;