ALTER TABLE timetable_frequent_summary_services
ADD COLUMN IF NOT EXISTS is_timing_point BOOLEAN;
