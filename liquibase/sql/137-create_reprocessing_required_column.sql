ALTER TABLE public."Timetable"
    ADD COLUMN IF NOT EXISTS reprocessing_required BOOLEAN;

CALL generate_license_lines_with_dq_issues(CURRENT_DATE);