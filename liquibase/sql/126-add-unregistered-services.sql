ALTER TABLE public."Timetable"
ADD COLUMN IF NOT EXISTS registered BOOLEAN;
