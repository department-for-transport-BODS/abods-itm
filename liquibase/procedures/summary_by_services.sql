create or replace procedure summary_by_services(IN partition_date date DEFAULT (CURRENT_DATE - '1 day'::interval))
    language plpgsql
as
$$
DECLARE
    tablename TEXT;

BEGIN
    tablename := 'timetable_summary_service_tz_' || to_char(partition_date, 'YYYY_MM_DD');

    IF NOT EXISTS (SELECT 1
                   FROM public."Timetable"
                   WHERE date_of_journey = partition_date) THEN
        RAISE NOTICE '% No timetable data for date %', clock_timestamp(), partition_date;
    ELSE
        RAISE NOTICE '% (Re)Creating partition public.%', clock_timestamp(), tablename;

        EXECUTE format(
                'CREATE TABLE IF NOT EXISTS public.%I PARTITION OF public.timetable_summary_service_tz FOR VALUES FROM (%L) TO (%L)',
                tablename,
                partition_date,
                partition_date + INTERVAL '1' DAY
                );

        EXECUTE format('ALTER TABLE public.%I OWNER TO abods_rw', tablename);

        RAISE NOTICE '% Deleting from %', clock_timestamp(), tablename;

        EXECUTE format(
                'DELETE FROM public.%I',
                tablename
                );

        RAISE NOTICE '% Generating and adding new data to %', clock_timestamp(), tablename;

        EXECUTE format(
                'INSERT INTO public.%I(
				operator_noc,
				line_name,
				noc_and_line_and_servicecode,
				date_of_journey,
				departure_hour,
				departure_hour_only,
				day_of_week,
				on_time_count,
				early_count,
				late_count,
				completed,
				scheduled,
				is_timing_point,
				max_early,
				max_late,
				avg_time_difference,
				admin_areas,
				estimated,
				incomplete_reason
			)
			SELECT
				sub.operator_noc,
				sub.line_name,
				sub.noc_and_line_and_servicecode,
				sub.date_of_journey,
				sub.departure_hour,
				sub.departure_hour_only,
				sub.day_of_week,
				sum(on_time_count) as on_time_count,
				sum(early_count) as early_count,
				sum(late_count) as late_count,
				sum(completed) as completed,
				sum(scheduled) as scheduled,
				sub.is_timing_point,
				sub.max_early,
				sub.max_late,
				COALESCE(ROUND(sum(sub.total_avg)/nullif(sum(completed), 0), 4), 0.0) AS avg_time_difference,
				sub.admin_area_id AS admin_areas,
				sub.estimated,
				sub.incomplete_reason
			FROM
				(
					SELECT
						ttb.operator_noc,
                        ttb.line_name,
						ttb.noc_and_line_and_servicecode,
						ttb.date_of_journey,
						ttb.departure_hour,
						ttb.departure_hour_only,
						ttb.day_of_week,
						ttb.on_time_count,
						ttb.early_count,
						ttb.late_count,
						ttb.completed,
						ttb.scheduled,
						ttb.is_timing_point,
						ttb.max_early,
						ttb.max_late,
						ttb.avg_time_difference,
						es.admin_area_id,
						ttb.estimated,
						ttb.incomplete_reason,
						completed * avg_time_difference as total_avg
					FROM
						public.timetable_summary_stops_tz ttb
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
				line_name,
				noc_and_line_and_servicecode,
				date_of_journey,
				day_of_week,
				departure_hour,
				departure_hour_only,
				is_timing_point,
				max_early,
				admin_area_id,
				max_late,
				estimated,
				incomplete_reason',
                tablename,
                partition_date,
                partition_date);
    END IF;

    RAISE NOTICE '% summary_by_services complete', clock_timestamp();
END;
$$;

alter procedure summary_by_services owner to abods_proxy_rw;
