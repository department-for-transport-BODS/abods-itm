create or replace procedure generate_license_lines_with_dq_issues(IN partition_date date)
    language plpgsql
as
$$
begin
    RAISE NOTICE '% (Re)Creating license_line_data_quality_isses table', clock_timestamp();

    DROP TABLE IF EXISTS public.license_line_data_quality_isses;

    execute format(
            '
            CREATE TABLE public.license_line_data_quality_isses AS
            SELECT
              *
            FROM
              (
                WITH service_code_list AS (
                  SELECT
                    registration_number,
                    split_service_number
                  FROM
                    bods.otc_service
                    CROSS JOIN LATERAL unnest(string_to_array(service_number, ''|'')) AS split_service_number
                  WHERE
                    (
                      split_service_number like ''%% %%''
                      OR LENGTH(split_service_number) > 4
                      OR split_service_number like ''%%[^a-zA-Z0-9]%%''
                    )
                ),
                timetable_list AS (
                  SELECT
                    DISTINCT service_code,
                    line_name
                  FROM
                    public."Timetable"
                  WHERE
                    date_of_journey >= %L::date - INTERVAL ''8 day''
                    AND date_of_journey < %L::date
                )
                SELECT
                  DISTINCT otc.registration_number,
                  otc.split_service_number AS otc_service_code,
                  t.line_name,
                  concat(split_part(t.service_code, '':'', 1), t.line_name) AS dq_issues_license_line
                FROM
                  service_code_list otc
                  LEFT JOIN timetable_list t ON REPLACE(t.service_code, '':'', ''/'') = otc.registration_number
                WHERE
                  t.service_code IS NOT NULL
              );
	        ',
            partition_date,
            partition_date
            );


    RAISE NOTICE '% License_line_data_quality_isses completed', clock_timestamp();
end;
$$;

alter procedure generate_license_lines_with_dq_issues owner to abods_proxy_rw;
