ALTER TABLE public."Timetable"
    ADD COLUMN IF NOT EXISTS registered BOOLEAN;

ALTER TABLE public."Tokens" 
ADD COLUMN data_monitoring_access_count INT,
ADD COLUMN data_monitoring_last_accessed TIMESTAMP;