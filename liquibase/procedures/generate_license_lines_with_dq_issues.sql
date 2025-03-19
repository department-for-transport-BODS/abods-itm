CREATE OR REPLACE PROCEDURE public.generate_license_lines_with_dq_issues(IN partition_date date)
 LANGUAGE plpgsql
AS $$

declare
    longdatestring   text := to_char(partition_date, 'YYYY_MM_DD');

begin


   

    RAISE NOTICE '% (Re)Creating license_line_data_quality_isses table', clock_timestamp();

    DROP TABLE IF EXISTS public.license_line_data_quality_isses;

    execute format(
            '
            CREATE TABLE public.license_line_data_quality_isses AS
			            SELECT
              *
            FROM
            (with service_code_list as(
			select registration_number , split_service_number
			FROM  bods.otc_service
			CROSS JOIN LATERAL unnest(string_to_array(service_number, ''|'')) AS split_service_number
			where (split_service_number like ''%% %%'' or LENGTH(split_service_number) > 4 or split_service_number like ''%%[^a-zA-Z0-9]%%'')),
			timetable_list as (
			select distinct service_code, line_name
			from public."Timetable"
			where date_of_journey >= %L::date - INTERVAL ''8 day'' AND date_of_journey < %L::date )
			select distinct otc.registration_number, 
				otc.split_service_number as otc_service_code, 
				t.line_name,                   
				concat(
                      split_part(t.service_code, '':'', 1),
                      t.line_name
                    ) AS dq_issues_license_line
                    from service_code_list otc
			left join timetable_list t on REPLACE(t.service_code, '':'', ''/'') = otc.registration_number
			where t.service_code is not null);
	        ',
            partition_date,
            partition_date
            );


    RAISE NOTICE '% License_line_data_quality_isses completed', clock_timestamp();
end;
$$
;
