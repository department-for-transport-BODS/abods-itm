CREATE OR REPLACE PROCEDURE public.create_timetable_threshold_summary(IN pt_date date)
 LANGUAGE plpgsql
AS $$

DECLARE
    partition_date date := pt_date;
    tablename      text;

BEGIN
    tablename := 'timetable_threshold_summary_' || to_char(partition_date, 'YYYY_MM_DD');

    IF NOT EXISTS (SELECT 1
                   FROM public."Timetable"
                   WHERE date_of_journey = partition_date) THEN
        RAISE NOTICE '% No timetable data for date %', clock_timestamp(), pt_date;
    ELSE
        RAISE NOTICE '% (Re)Creating partition public.%', clock_timestamp(), tablename;

        EXECUTE format(
                'CREATE TABLE IF NOT EXISTS public.%I PARTITION OF public.timetable_threshold_summary FOR VALUES FROM (%L) TO (%L)',
                tablename,
                partition_date,
                partition_date + interval '1' day
                );

        EXECUTE format('ALTER TABLE public.%I OWNER TO abods_rw', tablename);

        RAISE NOTICE '% Deleting from %', clock_timestamp(), tablename;

        EXECUTE format(
                'DELETE FROM public.%I',
                tablename
                );
        RAISE NOTICE '% Adding new data to %', clock_timestamp(), tablename;

        EXECUTE format(
            'INSERT INTO public.%I (
                operator_noc,
                line_name,
                noc_and_line_and_servicecode,
                service_name,
                time_diff_minutes,
                date_of_journey,
                is_timing_point,
                admin_areas,
                departure_hour,
                otp_count,
                day_of_week,
                estimated
            )
            SELECT operator_noc,
                   line_name,
                   noc_and_line_and_servicecode,
                   service_name,
                   time_diff_minutes,
                   date_of_journey,
                   is_timing_point,
                   ARRAY(SELECT DISTINCT UNNEST (array_admin)) AS array_admin_area,
                   departure_hour,
                   otp_count,
                   day_of_week,
                   estimated
            FROM
              (SELECT ttb.operator_noc,
                      ttb.line_name,
                      es.noc_and_line_and_servicecode,
                      es.service_name,
                      floor(ttb.time_difference::float/60) AS time_diff_minutes,
                      ttb.date_of_journey,
                      ttb.is_timing_point,
                      ARRAY_AGG(ttb.admin_area_id) OVER (PARTITION BY ttb.operator_noc, ttb.line_name, ttb.date_of_journey, ttb.is_timing_point) array_admin,
                      date_trunc(''hour'', ttb.expected_departure_time) AS departure_hour,
                      ttb.day_of_week,
                      count(*) AS otp_count,
                      estimated			
               FROM
                 (SELECT operator_noc,
                         line_name,
                         service_code,
                         CASE
                             WHEN timetable_id = first_value(timetable_id) OVER(PARTITION BY group_id, vehiclejourney_id
                                                                                ORDER BY group_id, expected_departure_time DESC, stop_index DESC)
                                  AND time_difference < 0 THEN 0
                             ELSE time_difference
                         END AS time_difference,
                         date_of_journey,
                         is_timing_point,
                         expected_departure_time,
                         day_of_week,
                         admin_area_id,
                         stop_index,
                         (timestamp_after_estimate IS NOT NULL) AS estimated,
						(previous_group_id IS NOT NULL) AS frequent_service, 
						(time_difference IS NULL) AS no_recorded
                  FROM public."Timetable"
                  WHERE date_of_journey = %L) ttb
               INNER JOIN public.expected_services es ON ttb.date_of_journey = es.date_of_journey
               AND ttb.operator_noc = es.operator_noc
               AND ttb.line_name = es.line_name
               AND ttb.service_code = split_part(es.noc_and_line_and_servicecode, ''-'', -1)      
            AND ttb.frequent_service = FALSE
			AND ttb.no_recorded = FALSE
               GROUP BY ttb.operator_noc,
                        ttb.line_name,
                        es.noc_and_line_and_servicecode,
                        es.service_name,
                        ttb.date_of_journey,
                        ttb.is_timing_point,
                        ttb.admin_area_id,
                        floor(ttb.time_difference::float/60),
                        DATE_TRUNC(''hour'', ttb.expected_departure_time),
                        ttb.day_of_week,
						ttb.estimated) x;',
                tablename,
                partition_date);
    END IF;

    RAISE NOTICE '% create_timetable_threshold_summary complete', clock_timestamp();
END;
$$
;
