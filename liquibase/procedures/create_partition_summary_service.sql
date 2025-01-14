create or replace procedure create_partition_summary_service()
    language plpgsql
as
$$
DECLARE
    partition_date date := current_date - interval '1 day';
    tablename      text;

BEGIN
    tablename := 'timetable_summary_service_' || to_char(partition_date, 'YYYY_MM_DD');

    RAISE NOTICE 'Creating partition if not exists %', tablename;

    IF EXISTS (SELECT 1
               FROM public."Timetable"
               WHERE date_of_journey = partition_date
               LIMIT 1) THEN
        RAISE NOTICE '(Re)Creating partition';

        EXECUTE format(
                'CREATE TABLE IF NOT EXISTS public.%I PARTITION OF public.timetable_summary_service FOR VALUES FROM (%L) TO (%L)',
                tablename,
                partition_date,
                partition_date + interval '1' day
                );

        EXECUTE format('ALTER TABLE public.%I OWNER TO abods_rw', tablename);

        ------------------------------
        -- Deleting from partition --
        ------------------------------

        RAISE NOTICE 'Deleting from partition';

        EXECUTE format(
                'DELETE FROM public.%I',
                tablename
                );

        ----- example insert my new data

        EXECUTE format(
                'INSERT INTO public.%I (
				operator_noc,
				line_name,
				noc_and_line,
				service_name,
				date_of_journey,
				departure_hour,
				day_of_week,
				on_time_count,
				early_count,
				late_count,
				completed,
				scheduled,
				is_timing_point,
				max_early,
				max_late,
				avg_time_difference
			)
			SELECT
				sub.operator_noc,
				sub.line_name,
				sub.noc_and_line,
				sub.service_name,
				sub.date_of_journey,
				date_trunc(''hour'', sub.expected_departure_time) AS departure_hour,
				sub.day_of_week,
				COUNT(CASE WHEN sub.otp_state = ''OnTime'' THEN 1 END) AS on_time_count,
				COUNT(CASE WHEN sub.otp_state = ''Early'' THEN 1 END) AS early_count,
				COUNT(CASE WHEN sub.otp_state = ''Late'' THEN 1 END) AS late_count,
				COUNT(sub.actual_departure_time) AS completed,
				COUNT(*) AS scheduled,
				sub.is_timing_point,
				sub.max_early,
				sub.max_late,
				COALESCE(AVG(sub.avg_time_difference/60.0), 0.0) AS avg_time_difference
			FROM
				(
					SELECT
						ttb.operator_noc,
						ttb.operator_name,
						es.line_name,
						es.noc_and_line,
						es.service_name,
						ttb.date_of_journey,
						ttb.day_of_week,
						ttb.expected_departure_time ,
						ttb.actual_departure_time,
						ttb.is_timing_point,
						ttb.otp_state,
						ttb.time_difference,
						ttb.stop_id,
						ttb.stop_latitude,
						ttb.stop_longitude,
						ttb.locality_id,
						CASE
							WHEN otp_state = ''Early'' AND time_difference >= -600 THEN 10
							WHEN otp_state = ''Early'' AND time_difference < -600 AND time_difference >= -1200 THEN 20
							WHEN otp_state = ''Early'' AND time_difference < -1200 AND time_difference >= -1800 THEN 30
							WHEN otp_state = ''Early'' AND time_difference < -1800 AND time_difference >= -2400 THEN 40
							WHEN otp_state = ''Early'' AND time_difference < -2400 AND time_difference >= -3000 THEN 50
							WHEN otp_state = ''Early'' AND time_difference < -3000 AND time_difference >= -3600 THEN 60
							WHEN otp_state = ''Early'' AND time_difference < -3600 THEN 70
							ELSE 0
						END AS max_early,
						CASE
							WHEN otp_state = ''Late'' AND time_difference <= 600 THEN 10
							WHEN otp_state = ''Late'' AND time_difference > 600 AND time_difference <= 1200 THEN 20
							WHEN otp_state = ''Late'' AND time_difference > 1200 AND time_difference <= 1800 THEN 30
							WHEN otp_state = ''Late'' AND time_difference > 1800 AND time_difference <= 2400 THEN 40
							WHEN otp_state = ''Late'' AND time_difference > 1800 AND time_difference <= 2400 THEN 40
							WHEN otp_state = ''Late'' AND time_difference > 2400 AND time_difference <= 3000 THEN 50
							WHEN otp_state = ''Late'' AND time_difference > 3000 AND time_difference <= 3600 THEN 60
							WHEN otp_state = ''Late'' AND time_difference > 3600 THEN 70
							ELSE 0
						END AS max_late,
						time_difference AS avg_time_difference
					FROM
						public."Timetable" ttb
					INNER JOIN public.expected_services es
						ON ttb.date_of_journey = es.date_of_journey
						AND ttb.operator_noc = es.operator_noc
						AND ttb.line_name = es.line_name
					WHERE
						ttb.date_of_journey = %L
				) AS sub
			WHERE
				date_of_journey = %L
			GROUP BY
				line_name,
				noc_and_line,
				service_name,
				operator_noc,
				date_of_journey,
				day_of_week,
				departure_hour,
				is_timing_point,
				max_early,
				max_late',
                tablename,
                partition_date,
                partition_date);

    END IF;

    partition_date := partition_date + interval '1' day;
-- END LOOP;
END;
$$;

alter procedure create_partition_summary_service() owner to abods_proxy_rw;
