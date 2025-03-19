ALTER TABLE public."Timetable"
    ADD COLUMN IF NOT EXISTS reprocessing_required BOOLEAN;

CREATE TABLE IF NOT EXISTS public.license_line_data_quality_issues
(
    registration_number    varchar(25),
    otc_service_code       text,
    line_name              text,
    dq_issues_license_line text
);

ALTER TABLE public.license_line_data_quality_issues OWNER TO abods_proxy_rw;

CALL generate_license_lines_with_dq_issues(CURRENT_DATE);
