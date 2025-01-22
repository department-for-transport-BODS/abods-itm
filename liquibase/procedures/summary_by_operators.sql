create or replace procedure summary_by_operators(IN partition_date date DEFAULT (CURRENT_DATE - '1 day'::interval))
    language plpgsql
as
$$

DECLARE
    tablename TEXT := 'timetable_summary_operator_t_' || to_char(partition_date, 'YYYY_MM_DD');

BEGIN
    RAISE NOTICE '% (Re)Creating partition public.%', clock_timestamp(), tablename;

    EXECUTE format(
            'CREATE TABLE if not exists public.%I partition of public.timetable_summary_operator_t FOR VALUES FROM (%L) TO (%L)',
            tablename,
            partition_date,
            partition_date + INTERVAL '1' DAY
            );

    EXECUTE format('
		ALTER TABLE public.%I OWNER TO abods_rw',
                   tablename
            );

    RAISE NOTICE '% Deleting from %', clock_timestamp(), tablename;

    EXECUTE format(
            'DELETE FROM public.%I',
            tablename
            );

    RAISE NOTICE '% Adding new data to %', clock_timestamp(), tablename;

    EXECUTE format(
            'INSERT INTO public.%I (
        operator_noc,
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
        incomplete_reason_1_count,
        incomplete_reason_2_count,
        incomplete_reason_3_count,
        incomplete_reason_4_count,
        incomplete_reason_5_count
    )
    SELECT
        sub.operator_noc,
        sub.date_of_journey,
        sub.departure_hour,
        sub.departure_hour_only,
        sub.day_of_week,
        SUM(sub.on_time_count) AS on_time_count,
        SUM(sub.early_count) AS early_count,
        SUM(sub.late_count) AS late_count,
        SUM(sub.completed) AS completed,
        SUM(sub.scheduled) AS scheduled,
        sub.is_timing_point,
        sub.max_early,
        sub.max_late,
        sub.avg_time_difference,
        sub.admin_areas,
		sub.estimated,
        SUM(sub.incomplete_reason_1_count) AS incomplete_reason_1_count,
        SUM(sub.incomplete_reason_2_count) AS incomplete_reason_2_count,
        SUM(sub.incomplete_reason_3_count) AS incomplete_reason_3_count,
        SUM(sub.incomplete_reason_4_count) AS incomplete_reason_4_count,
        SUM(sub.incomplete_reason_5_count) AS incomplete_reason_5_count
    FROM
        (
            SELECT
                operator_noc,
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
                incomplete_reason_1_count,
                incomplete_reason_2_count,
                incomplete_reason_3_count,
                incomplete_reason_4_count,
                incomplete_reason_5_count
            FROM
                public.timetable_summary_service_tz
            WHERE
                date_of_journey = %L
        ) AS sub
    WHERE
        date_of_journey = %L
    GROUP BY
        operator_noc,
        date_of_journey,
        day_of_week,
        departure_hour,
        departure_hour_only,
        is_timing_point,
        max_early,
        max_late,
        avg_time_difference,
        admin_areas,
		estimated',
            tablename,
            partition_date,
            partition_date
            );

    RAISE NOTICE '% summary_by_operators complete', clock_timestamp();
END;
$$;

alter procedure summary_by_operators owner to abods_proxy_rw;
