CREATE OR REPLACE PROCEDURE summary_by_stops(
    IN partition_date DATE DEFAULT (CURRENT_DATE - '1 day'::INTERVAL)
)
LANGUAGE plpgsql
AS
$$
DECLARE
    longdatestring TEXT := to_char(partition_date, 'YYYY_MM_DD');
    tablename TEXT;
BEGIN
    RAISE NOTICE 'Starting summary_by_stops for %', partition_date;
    tablename := concat('timetable_summary_stops_tz_', longdatestring);

    IF NOT EXISTS (
        SELECT relname
        FROM pg_class
        WHERE relname = concat('Timetable_p', longdatestring)
    ) THEN
        RAISE NOTICE '% No timetable data for date %', clock_timestamp(), partition_date;
    ELSE
        -- Check for existence of dated table
        IF NOT EXISTS (
            SELECT relname 
            FROM pg_class 
            WHERE relname = tablename
        ) THEN
            RAISE NOTICE 'Dated table % not found', tablename;
            RAISE NOTICE 'Creating table %', tablename;

            -- Create partition table initially unattached
            EXECUTE FORMAT(
                'CREATE TABLE public.%I (LIKE public.%I INCLUDING ALL);',
                tablename,
                'timetable_summary_stops_tz'
            );

            EXECUTE FORMAT('ALTER TABLE public.%I OWNER TO abods_rw', tablename);
        ELSE
            RAISE NOTICE 'Dated table % found', tablename;
            RAISE NOTICE '% Deleting from %', clock_timestamp(), tablename;
            EXECUTE FORMAT('DELETE FROM public.%I', tablename);
        END IF;

        RAISE NOTICE '% Adding new data to %', clock_timestamp(), tablename;
		RAISE NOTICE 'Starting data aggregation and insert...';

      
		RAISE NOTICE 'Running main EXECUTE for journeys_with_previous_stop_departure and insert...';
		EXECUTE format('WITH 
					expected_journeys_for_date AS(
						select * from public.expected_journeys
						where date_of_journey = %L
					),
					journeys_with_previous_stop_departure AS(
					SELECT
						ttb.timetable_id,
						ttb.operator_noc,
						ttb.service_code,
						ej.noc_and_line_and_servicecode,
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
						ttb.stop_index,
						ttb.direction,
						ttb.group_id,
						ttb.vehiclejourney_id,
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
						(ttb.timestamp_after_estimate is not null) AS estimated,
						LAG(ttb.expected_departure_time) OVER (PARTITION BY ttb.group_id, ttb.vehiclejourney_id ORDER BY ttb.expected_departure_time, ttb.stop_index) AS previous_stop_expected_departure,
						LAG(COALESCE(ttb.actual_departure_time, ttb.timestamp_after_estimate)) OVER (PARTITION BY ttb.group_id, ttb.vehiclejourney_id ORDER BY ttb.expected_departure_time, ttb.stop_index) AS previous_stop_actual_departure,
						ttb.incomplete_reason AS incomplete_reason
					FROM
					public.%I ttb
						INNER JOIN expected_journeys_for_date ej
							ON ttb.operator_noc = ej.operator_noc
							AND ttb.line_name = ej.line_name
							AND ttb.service_code = split_part(
								ej.noc_and_line_and_servicecode,
								''-''
								, -1)
							AND ttb.journey_code = ej.journey_code
							AND ttb.direction = ej.direction
					WHERE
						ttb.previous_group_id IS NULL
						AND ej.is_cancelled = FALSE
				),
				journeys_filtered_with_timing_points AS (
					SELECT
						timetable_id,
						LAG(expected_departure_time) OVER (PARTITION BY group_id, vehiclejourney_id ORDER BY expected_departure_time) AS previous_timing_point_expected_departure,
						LAG(actual_departure_time) OVER (PARTITION BY group_id, vehiclejourney_id ORDER BY expected_departure_time) AS previous_timing_point_actual_departure
					FROM
						journeys_with_previous_stop_departure
					WHERE
						is_timing_point = true
				)
				INSERT INTO public.%I(
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
				direction,
				stop_index,
				count_delayed,
				average_delay,
				diff_sched_time_to_stop,
				diff_sched_time_to_stop_timing_point,
				diff_actual_time_to_stop,
				diff_actual_time_to_stop_timing_point,
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
				COALESCE(AVG(sub.time_difference/60.0), 0.0) AS avg_time_difference,
				sub.estimated,
				sub.direction,
					sub.stop_index,
					COUNT(sub.time_difference) FILTER (WHERE sub.time_difference > 0) as count_delayed,
					AVG(sub.time_difference) FILTER(WHERE sub.time_difference > 0) as average_delay,
					AVG(EXTRACT(EPOCH FROM (sub.expected_departure_time - sub.previous_stop_expected_departure)))
    					FILTER (WHERE sub.expected_departure_time IS NOT NULL 
										AND sub.actual_departure_time IS NOT NULL
										AND sub.previous_stop_expected_departure IS NOT NULL
										AND sub.previous_stop_actual_departure IS NOT NULL
								) as diff_sched_time_to_stop,
					AVG(EXTRACT(EPOCH FROM (sub.expected_departure_time - tp_sub.previous_timing_point_expected_departure)))
    					FILTER (WHERE sub.expected_departure_time IS NOT NULL 
										AND sub.actual_departure_time is NOT NULL
										AND tp_sub.previous_timing_point_actual_departure is NOT NULL
										AND tp_sub.previous_timing_point_expected_departure IS NOT NULL
								) as diff_sched_time_to_stop_timing_point,
					AVG(EXTRACT(EPOCH FROM (sub.actual_departure_time - sub.previous_stop_actual_departure)))
    					FILTER (WHERE sub.actual_departure_time IS NOT NULL
										AND sub.expected_departure_time IS NOT NULL 
										AND sub.previous_stop_expected_departure IS NOT NULL
										AND sub.previous_stop_actual_departure IS NOT NULL
								) as diff_actual_time_to_stop,
					AVG(EXTRACT(EPOCH FROM (sub.actual_departure_time - tp_sub.previous_timing_point_actual_departure)))
    					FILTER (WHERE sub.actual_departure_time IS NOT NULL 
										AND sub.expected_departure_time IS NOT NULL
										AND tp_sub.previous_timing_point_expected_departure IS NOT NULL 
										AND tp_sub.previous_timing_point_actual_departure IS NOT NULL
								) as diff_actual_time_to_stop_timing_point,
				sub.incomplete_reason
			FROM
				journeys_with_previous_stop_departure sub
				LEFT JOIN journeys_filtered_with_timing_points tp_sub
					ON sub.timetable_id = tp_sub.timetable_id
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
					direction,
					stop_index,
					incomplete_reason',
				partition_date,
                concat('Timetable_p', longdatestring),
                tablename);

        ----------------------------
        -- Attaching new partition --
        ----------------------------

        -- Check if partition is attached to master table
        IF NOT EXISTS (
            SELECT
                p.relname AS parent,
                c.relname AS child 
            FROM pg_inherits i 
            JOIN pg_class p ON i.inhparent = p.oid
            JOIN pg_class c ON i.inhrelid = c.oid
            WHERE p.relname = 'timetable_summary_stops_tz'
              AND c.relname LIKE tablename
        ) THEN
            RAISE NOTICE 'Dated table % not attached to %', tablename, 'timetable_summary_stops_tz';
            RAISE NOTICE 'Attaching table % to %', tablename, 'timetable_summary_stops_tz';

            -- Attach table if it isn't attached
            EXECUTE FORMAT(
                'ALTER TABLE public.%I
                 ATTACH PARTITION public.%I
                 FOR VALUES FROM (%L) TO (%L);',
                'timetable_summary_stops_tz',
                tablename,
                partition_date,
                partition_date + INTERVAL '1' DAY
            );
        ELSE
            RAISE NOTICE 'Dated table % already attached to %', tablename, 'timetable_summary_stops_tz';
        END IF;
    END IF;

    RAISE NOTICE '% summary_by_stops complete', clock_timestamp();
    RAISE NOTICE 'Finished summary_by_stops for %', partition_date;
END;
$$;
