CREATE OR REPLACE PROCEDURE public.summary_by_stops(IN partition_date date DEFAULT (CURRENT_DATE - '1 day'::interval))
 LANGUAGE plpgsql
AS $procedure$
DECLARE
	tablename TEXT;

BEGIN
	tablename := 'timetable_summary_stops_tz_' || to_char(partition_date, 'YYYY_MM_DD');

	RAISE NOTICE 'Creating timetable_summary_stops_tz partition if not exists %', tablename;

	IF EXISTS (
		SELECT 1
		FROM public."Timetable"
		WHERE date_of_journey = partition_date
	) THEN
		RAISE NOTICE '(Re)Creating timetable_summary_stops_tz partition';

		EXECUTE format(
			'CREATE TABLE IF NOT EXISTS public.%I PARTITION OF public.timetable_summary_stops_tz FOR VALUES FROM (%L) TO (%L)',
			tablename,
			partition_date,
			partition_date + INTERVAL '1' DAY
		);

		EXECUTE format('ALTER TABLE public.%I OWNER TO abods_rw', tablename);

		------------------------------
		-- Deleting from partition --
		------------------------------

		RAISE NOTICE 'Deleting from timetable_summary_stops_tz partition';

		EXECUTE format(
			'DELETE FROM public.%I',
			tablename
		);

		----- example insert my new data

		RAISE NOTICE 'Adding new data TO timetable_summary_stops_tz partition';

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
				headway_stops_count,
				expected_headway,
				actual_headway,
				excess_wait_Time,
				estimated, 
				frequent_service
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
				COUNT(sub.actual_headway) AS headway_stops_count,
				AVG(sub.expected_headway) AS expected_headway,
				AVG(sub.actual_headway) FILTER (WHERE sub.actual_headway IS NOT NULL) AS actual_headway,
				AVG(sub.headway_time_difference) FILTER (WHERE sub.actual_headway IS NOT NULL) AS excess_wait_Time,
				sub.estimated,
				sub.frequent_service
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
					ttb.expected_headway,
					ttb.actual_headway,
					ttb.headway_time_difference,
					(ttb.timestamp_after_estimate is not null) AS estimated,
					(ttb.previous_group_id is not null) AS frequent_service
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
					frequent_service',
            tablename,
            partition_date,
            partition_date);

		-- EXECUTE format(query, tablename, partition_date, partition_date);
	END IF;

	partition_date := partition_date + INTERVAL '1' DAY;
-- END LOOP;
END;
$procedure$
;
