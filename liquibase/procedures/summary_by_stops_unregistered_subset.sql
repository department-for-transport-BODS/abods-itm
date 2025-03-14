create or replace procedure summary_by_stops_unregistered_subset(IN partition_date date DEFAULT (CURRENT_DATE - '1 day'::interval))
    language plpgsql
as
$$
DECLARE
    tablename TEXT;

BEGIN
    tablename := 'timetable_summary_stops_tz_' || to_char(partition_date, 'YYYY_MM_DD');

    IF NOT EXISTS (SELECT 1
                   FROM public."Timetable"
                   WHERE date_of_journey = partition_date) THEN
        RAISE NOTICE '% No timetable data for date %', clock_timestamp(), partition_date;
    ELSE
        RAISE NOTICE '% (Re)Creating partition public.%', clock_timestamp(), tablename;

        EXECUTE format(
                'CREATE TABLE IF NOT EXISTS public.%I PARTITION OF public.timetable_summary_stops_tz FOR VALUES FROM (%L) TO (%L)',
                tablename,
                partition_date,
                partition_date + INTERVAL '1' DAY
                );

        EXECUTE format('ALTER TABLE public.%I OWNER TO abods_rw', tablename);

        RAISE NOTICE '% Adding new data to %', clock_timestamp(), tablename;

        EXECUTE format(
                'INSERT INTO public.%I(
				operator_noc,
				service_code,
				noc_and_line_and_servicecode,
				stop_id,
				locality_id,
				line_name,
				stop_latitude,
				stop_longitude,
				date_of_journey,
				departure_hour,
				departure_hour_only,
				day_of_week,
				on_time_count,
				early_count,
				late_count,
				completed,
				scheduled,
				common_name,
				is_timing_point,
				max_early,
				max_late,
				avg_time_difference,
				estimated,
				incomplete_reason
			)
			SELECT
				sub.operator_noc,
				sub.service_code,
				sub.noc_and_line_and_servicecode,
				sub.stop_id,
				sub.locality_id,
				sub.line_name,
				sub.stop_latitude,
				sub.stop_longitude,
				sub.date_of_journey,
				date_trunc(''hour'', sub.expected_departure_time::timestamptz) AS departure_hour,
				(EXTRACT(HOUR FROM sub.expected_departure_time)::text || '':00:00'' ||
					CASE
						WHEN RIGHT(sub.expected_departure_time::text, 6)~ ''^[+-]'' THEN RIGHT(sub.expected_departure_time::text, 6)
						ELSE ''+00''
					END
				)::timetz AS departure_hour_only,
				sub.day_of_week,
				COUNT(CASE WHEN sub.otp_state = ''OnTime'' THEN 1 END) AS on_time_count,
				COUNT(CASE WHEN sub.otp_state = ''Early'' THEN 1 END) AS early_count,
				COUNT(CASE WHEN sub.otp_state = ''Late'' THEN 1 END) AS late_count,
				COUNT(sub.actual_departure_time) AS completed,
				COUNT(*) AS scheduled,
				sub.common_name,
				sub.is_timing_point,
				sub.max_early,
				sub.max_late,
				COALESCE(AVG(sub.avg_time_difference/60.0), 0.0) AS avg_time_difference,
				sub.estimated,
				sub.incomplete_reason
			FROM
				(
					SELECT
					ttb.operator_noc,
					ttb.service_code,
					es.noc_and_line_and_servicecode,
					ttb.stop_id,
					ttb.locality_id,
					ttb.line_name,
					ttb.date_of_journey,
					ttb.day_of_week,
					ttb.common_name,
					ttb.expected_departure_time,
					COALESCE(ttb.actual_departure_time, ttb.timestamp_after_estimate) as actual_departure_time,
					ttb.is_timing_point,
					ttb.otp_state,
					ttb.time_difference,
					ttb.stop_latitude,
					ttb.stop_longitude,
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
						WHEN otp_state = ''Late'' AND time_difference > 2400 AND time_difference <= 3000 THEN 50
						WHEN otp_state = ''Late'' AND time_difference > 3000 AND time_difference <= 3600 THEN 60
						WHEN otp_state = ''Late'' AND time_difference > 3600 THEN 70
						ELSE 0
					END AS max_late,
					ttb.time_difference AS avg_time_difference,
					(ttb.timestamp_after_estimate is not null) AS estimated,
					ttb.incomplete_reason AS incomplete_reason
				FROM
					public."Timetable" ttb
					INNER JOIN public.expected_services es
						ON ttb.date_of_journey = es.date_of_journey
						AND ttb.operator_noc = es.operator_noc
						AND ttb.line_name = es.line_name
						AND ttb.service_code = split_part(
							es.noc_and_line_and_servicecode,
							''-''
							, -1)
					WHERE
						ttb.date_of_journey = %L
						and ttb.previous_group_id is null
						and ttb.reprocessing_required = True
				) AS sub
				WHERE
					date_of_journey = %L
				GROUP BY
					operator_noc,
					service_code,
					noc_and_line_and_servicecode,
					stop_id,
					locality_id,
					line_name,
					stop_latitude,
					stop_longitude,
					date_of_journey,
					departure_hour,
					departure_hour_only,
					day_of_week,
					common_name,
					is_timing_point,
					max_early,
					max_late,
					estimated,
					incomplete_reason',
                tablename,
                partition_date,
                partition_date);
    END IF;

    RAISE NOTICE '% summary_by_stops complete', clock_timestamp();
END;
$$;

alter procedure summary_by_stops_unregistered_subset owner to abods_proxy_rw;
