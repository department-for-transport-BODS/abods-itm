-- Excess wait time null would indicate no stops are matched
-- as opposed to 0 where excess wait time is 0 for journeys
ALTER TABLE public.timetable_frequent_summary_services
    ALTER COLUMN excess_wait_Time DROP NOT NULL;

ALTER TABLE public.timetable_frequent_summary_services
    ALTER COLUMN expected_headway DROP NOT NULL;

ALTER TABLE public.timetable_frequent_summary_services
    ALTER COLUMN actual_headway DROP NOT NULL;
