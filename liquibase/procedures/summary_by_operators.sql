create or replace procedure summary_by_operators(IN partition_date date DEFAULT (CURRENT_DATE - '1 day'::interval))
    language plpgsql
as
$$

DECLARE
    tablename TEXT := 'timetable_summary_operator_t_' || to_char(partition_date, 'YYYY_MM_DD');

BEGIN
    RAISE NOTICE 'Creating timetable_summary_operator_t partition if not exists %', tablename;
    RAISE NOTICE '(Re)Creating timetable_summary_operator_t partition';

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

    ------------------------------
    -- Deleting from partition --
    ------------------------------

    RAISE NOTICE 'Deleting from timetable_summary_operator_t partition';

    EXECUTE format(
            'DELETE FROM public.%I',
            tablename
            );

    ----- example insert my new data

    RAISE NOTICE 'Adding new data to timetable_summary_operator_t partition';

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
		estimated
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
		sub.estimated
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
				estimated
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
END;
$$;
