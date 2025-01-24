CREATE OR REPLACE PROCEDURE public.incomplete_data_load(IN partition_date date DEFAULT (CURRENT_DATE - '1 day'::interval))
 LANGUAGE plpgsql
AS $procedure$
declare
    longdatestring text := to_char(partition_date, 'YYYY_MM_DD');
 
begin

RAISE NOTICE '% Start running incomplete_data_load ', clock_timestamp();

RAISE NOTICE '% Creating existing operator nocs table', clock_timestamp();

execute format('
            create table public.%I as
            select timetable_id
            from public."Timetable" t
            join public."SiriVMPositions" s
            on t.operator_noc = s.operator_ref
            where t.date_of_journey = %L
            and s.date_of_journey = %L
        ', 
            concat('existing_operator_nocs_', longdatestring),
            partition_date,
            partition_date);

RAISE NOTICE '% Created existing operator nocs table', clock_timestamp();

execute format('
            create table public.%I as
            select timetable_id
            from public."Timetable" t
            join public."SiriVMPositions" s
            on t.line_name = s.line_name
            where t.date_of_journey = %L
            and s.date_of_journey = %L
        ', 
            concat('existing_line_name_', longdatestring),
            partition_date,
            partition_date);

RAISE NOTICE '% Created existing line name table', clock_timestamp();

execute format('
            create table public.%I as
            select timetable_id
            from public."Timetable" t
            join public."SiriVMPositions" s
            on t.journey_code = s.journey_ref
            where t.date_of_journey = %L
            and s.date_of_journey = %L
        ', 
            concat('existing_journey_code_', longdatestring),
            partition_date,
            partition_date);

RAISE NOTICE '% Created existing journey code table', clock_timestamp();

RAISE NOTICE '% Creating stops without operator nocs table', clock_timestamp();
 
execute format('
            create table public.%I as
            select distinct timetable_id
            from public."Timetable"
            where date_of_journey = %L
            and actual_departure_time IS NULL
            and time_difference IS NULL
            and timetable_id not in (select timetable_id from public.%I)
            and timetable_id in (select timetable_id from public.%I)
            and timetable_id in (select timetable_id from public.%I)',
            concat('stops_wo_nocs_', longdatestring),
            partition_date,
            concat('existing_operator_nocs_', longdatestring),
            concat('existing_journey_code_', longdatestring),
            concat('existing_line_name_', longdatestring)
            );

RAISE NOTICE '% Created stops without operator nocs table', clock_timestamp();

RAISE NOTICE '% Creating stops without service table', clock_timestamp();

execute format('
            create table public.%I as
            select distinct timetable_id
            from public."Timetable"
            where date_of_journey = %L
            and actual_departure_time IS NULL
            and time_difference IS NULL
            and timetable_id not in (select timetable_id from public.%I)
            and timetable_id in (select timetable_id from public.%I)
            and timetable_id in (select timetable_id from public.%I)',
            concat('stops_wo_service_', longdatestring),
            partition_date,
            concat('existing_line_name_', longdatestring),
            concat('existing_operator_nocs_', longdatestring),
            concat('existing_journey_code_', longdatestring)
            );

RAISE NOTICE '% Created stops without service table', clock_timestamp();

RAISE NOTICE '% Creating stops without journey code table', clock_timestamp();

execute format('
            create table public.%I as
            select distinct timetable_id
            from public."Timetable"
            where date_of_journey = %L
            and actual_departure_time IS NULL
            and time_difference IS NULL
            and timetable_id not in (select timetable_id from public.%I)
            and timetable_id in (select timetable_id from public.%I)
            and timetable_id in (select timetable_id from public.%I)',
            concat('stops_wo_journey_code_', longdatestring),
            partition_date,
            concat('existing_journey_code_', longdatestring),
            concat('existing_line_name_', longdatestring),
            concat('existing_operator_nocs_', longdatestring)
            );

RAISE NOTICE '% Created stops without journey code table', clock_timestamp();

RAISE NOTICE '% Creating stops without gps in zone table', clock_timestamp();

execute format('
            create table public.%I as
            select distinct timetable_id
            from public."Timetable"
            where timetable_id not in
            (select distinct t.timetable_id
            FROM public."Timetable" t
            join public."SiriVMPositions" s
            on t.group_id = s.group_id
            where t.actual_departure_time IS NULL
            and t.time_difference IS NULL
            and s.date_of_journey = %L
            and (2 * ASIN(SQRT(POWER(SIN((RADIANS(t.stop_latitude) - RADIANS(s.latitude)) / 2), 2) + COS(RADIANS(s.latitude)) * COS(RADIANS(t.stop_latitude)) * POWER(SIN((RADIANS(s.longitude) - RADIANS(t.stop_longitude)) / 2), 2))) * 6371) * 1000 <= 70
            and t.date_of_journey = %L)
            and t.date_of_journey = %L',
            concat('stops_wo_gps_in_zone_', longdatestring),
            partition_date,
            partition_date,
            partition_date);

RAISE NOTICE '% Created stops without gps in zone table', clock_timestamp();

RAISE NOTICE '% Creating stops with invalid gps in zone table', clock_timestamp();

execute format('
            create table public.%I as
            (select distinct timetable_id
            FROM public."Timetable" t
            join public."SiriVMPositions" s
            on t.group_id = s.group_id
            where t.date_of_journey = %L
            and s.date_of_journey = %L
            and t.actual_departure_time IS NULL
            and t.time_difference IS NULL
            and (2 * ASIN(SQRT(POWER(SIN((RADIANS(t.stop_latitude) - RADIANS(s.latitude)) / 2), 2) + COS(RADIANS(s.latitude)) * COS(RADIANS(t.stop_latitude)) * POWER(SIN((RADIANS(s.longitude) - RADIANS(t.stop_longitude)) / 2), 2))) * 6371) * 1000 <= 70
        )',
            concat('stops_w_invalid_gps_in_zone', longdatestring),
            partition_date,
            partition_date);

RAISE NOTICE '% Created stops with invalid gps in zone table', clock_timestamp();

RAISE NOTICE '% Populating incomplete reason column in timetable', clock_timestamp();

execute format('
            UPDATE public."Timetable"
            SET incomplete_reason = 1
            where timetable_id IN (select timetable_id from %I)
            and date_of_journey = %L',
            concat('stops_wo_nocs_', longdatestring),
            partition_date);

execute format('
            UPDATE public."Timetable"
            SET incomplete_reason = 2
            where timetable_id IN (select timetable_id from %I)
            and date_of_journey = %L',
            concat('stops_wo_service_', longdatestring),
            partition_date);

execute format('
            UPDATE public."Timetable"
            SET incomplete_reason = 3
            where timetable_id IN (select timetable_id from %I)
            and date_of_journey = %L',
            concat('stops_wo_journey_code_', longdatestring),
            partition_date);

execute format('
            UPDATE public."Timetable"
            SET incomplete_reason = 4
            where timetable_id IN (select timetable_id from %I)
            and date_of_journey = %L',
            concat('stops_wo_gps_in_zone_', longdatestring),
            partition_date);

execute format('
            UPDATE public."Timetable"
            SET incomplete_reason = 5
            where timetable_id IN (select timetable_id from %I)
            and date_of_journey = %L',
            concat('stops_w_invalid_gps_in_zone', longdatestring),
            partition_date);

RAISE NOTICE '% Dropping temp tables', clock_timestamp();

execute format('drop table if exists public.%I', concat('existing_line_name_', longdatestring));
execute format('drop table if exists public.%I', concat('existing_journey_code_', longdatestring));
execute format('drop table if exists public.%I', concat('existing_operator_nocs_', longdatestring));
execute format('drop table if exists public.%I', concat('stops_wo_nocs_', longdatestring));
execute format('drop table if exists public.%I', concat('stops_wo_service_', longdatestring));
execute format('drop table if exists public.%I', concat('stops_wo_journey_code_', longdatestring));
execute format('drop table if exists public.%I', concat('stops_wo_gps_in_zone_', longdatestring));
execute format('drop table if exists public.%I', concat('stops_w_invalid_gps_in_zone', longdatestring));

RAISE NOTICE '% incomplete_data_load complete', clock_timestamp();
end;
$procedure$
;