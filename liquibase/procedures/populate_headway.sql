CREATE OR REPLACE PROCEDURE public.populate_headway(IN pt_date date)
 LANGUAGE plpgsql
AS $procedure$
DECLARE
    partition_date DATE := pt_date;
BEGIN
    RAISE NOTICE '% Creating temp_timetable_headway', clock_timestamp();

    EXECUTE format(
            'drop table if exists public.temp_timetable_headway;'
            );

    EXECUTE format(
            'create table public.temp_timetable_headway
        as
        select *, extract( epoch from x.actual_departure_time - x.previous_actual_departure_time ) as actual_headway from
        ( select
        timetable_id,
        COALESCE(actual_departure_time, timestamp_after_estimate) as actual_departure_time,
        lag(COALESCE(actual_departure_time, timestamp_after_estimate)) over(partition by operator_noc,line_name,date_of_journey,stop_id,stop_index
        order by stop_id,stop_index asc , expected_departure_time  asc) as previous_actual_departure_time
        from public."Timetable" t
        where date_of_journey = %L and previous_group_id is not null
        and (actual_departure_time is not null or timestamp_after_estimate is not null)
        )  x where x.previous_actual_departure_time is not null;',
            partition_date
            );

    RAISE NOTICE '% Updating timetable table with headway data', clock_timestamp();

    EXECUTE format(
            'update public."Timetable" y

        set headway_time_difference = y.expected_headway - x.actual_headway ,
        actual_headway = x.actual_headway
        from public.temp_timetable_headway x
        where x.timetable_id  = y.timetable_id
        and y.date_of_journey = %L;',
            partition_date
            );


    RAISE NOTICE '% Dropping temp tables', clock_timestamp();

    EXECUTE format(
            'drop table if exists public.temp_timetable_headway;'
            );

    RAISE NOTICE '% populate_headway complete', clock_timestamp();
END;
$procedure$
;
