CREATE OR REPLACE PROCEDURE public.incomplete_data_load(IN partition_date date DEFAULT (CURRENT_DATE - '1 day'::interval))
 LANGUAGE plpgsql
AS $procedure$
declare
    longdatestring text := to_char(partition_date, 'YYYY_MM_DD');
 
begin

RAISE NOTICE '% Start running incomplete_data_load ', clock_timestamp();

RAISE NOTICE '% Creating stops without operator nocs table', clock_timestamp();
 
execute format('
            CREATE TABLE public.%I AS
            SELECT timetable_id
            FROM public."Timetable" t
            WHERE date_of_journey = %L
                AND actual_departure_time IS NULL
                AND time_difference IS NULL
                AND NOT EXISTS (
                    SELECT 1
                    FROM public."Timetable" t2
                    JOIN public."SiriVMPositions" s ON t2.operator_noc = s.operator_ref
                    WHERE t2.timetable_id = t.timetable_id
                        AND t2.date_of_journey = %L
                        AND s.date_of_journey = %L
                );',
            concat('stops_wo_nocs_', longdatestring),
            partition_date,
            partition_date,
			partition_date
            );

RAISE NOTICE '% Created stops without operator nocs table', clock_timestamp();


RAISE NOTICE '% Creating stops without journey code table', clock_timestamp();

execute format('
            CREATE TABLE public.%I AS
            SELECT timetable_id
            FROM public."Timetable" t
            WHERE date_of_journey = %L
                AND actual_departure_time IS NULL
                AND time_difference IS NULL
                AND NOT EXISTS (
                    SELECT 1
                    FROM public."Timetable" t2
                    JOIN public."SiriVMPositions" s ON t2.group_id = s.group_id
                    WHERE t2.timetable_id = t.timetable_id
                        AND t2.date_of_journey = %L
                        AND s.date_of_journey = %L
                )
                AND EXISTS (
                    SELECT 1
                    FROM public."Timetable" t3
                    JOIN public."SiriVMPositions" s ON t3.operator_noc = s.operator_ref and t3.line_name = s.line_name
                    WHERE t3.timetable_id = t.timetable_id
                        AND t3.date_of_journey = %L
                        AND s.date_of_journey = %L
                );',
            concat('stops_wo_journey_code_', longdatestring),
            partition_date,
            partition_date,
			partition_date,
			partition_date,
			partition_date
            );

RAISE NOTICE '% Created stops without journey code table', clock_timestamp();

RAISE NOTICE '% Creating stops without service table', clock_timestamp();

execute format('
            CREATE TABLE public.%I AS
            SELECT timetable_id
            FROM public."Timetable" t
            WHERE date_of_journey = %L
                AND actual_departure_time IS NULL
                AND time_difference IS NULL
                AND NOT EXISTS (
                    SELECT 1
                    FROM public."Timetable" t2
                    JOIN public."SiriVMPositions" s ON t2.group_id = s.group_id
                    WHERE t2.timetable_id = t.timetable_id
                        AND t2.date_of_journey = %L
                        AND s.date_of_journey = %L
                )
                AND NOT EXISTS (
                    SELECT 1
                    FROM public.%I
                    WHERE timetable_id = t.timetable_id
                )
                AND EXISTS (
                    SELECT 1
                    FROM public."Timetable" t3
                    JOIN public."SiriVMPositions" s ON t3.operator_noc = s.operator_ref
                    WHERE t3.timetable_id = t.timetable_id
                        AND t3.date_of_journey = %L
                        AND s.date_of_journey = %L
                );',
            concat('stops_wo_service_', longdatestring),
            partition_date,
            partition_date,
			partition_date,
            concat('stops_wo_journey_code_', longdatestring),
            partition_date,
			partition_date
            );

RAISE NOTICE '% Created stops without service table', clock_timestamp();

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

RAISE NOTICE '% Creating stops without gps in zone table', clock_timestamp();

execute format('
            CREATE TABLE public.%I AS
            SELECT distinct timetable_id
            FROM public."Timetable" t
            join public."SiriVMPositions" s
            on t.group_id = s.group_id
            WHERE t.date_of_journey = %L
            AND s.date_of_journey = %L
            AND t.actual_departure_time IS NULL
            AND t.time_difference IS NULL
            AND NOT EXISTS (
                SELECT 1
                FROM public.%I t2
                WHERE t2.timetable_id = t.timetable_id
            );',
            concat('stops_wo_gps_in_zone_', longdatestring),
            partition_date,
            partition_date,
            concat('stops_w_invalid_gps_in_zone', longdatestring));

RAISE NOTICE '% Created stops without gps in zone table', clock_timestamp();

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

execute format('drop table if exists public.%I', concat('stops_wo_nocs_', longdatestring));
execute format('drop table if exists public.%I', concat('stops_wo_service_', longdatestring));
execute format('drop table if exists public.%I', concat('stops_wo_journey_code_', longdatestring));
execute format('drop table if exists public.%I', concat('stops_wo_gps_in_zone_', longdatestring));
execute format('drop table if exists public.%I', concat('stops_w_invalid_gps_in_zone', longdatestring));

RAISE NOTICE '% incomplete_data_load complete', clock_timestamp();
end;
$procedure$
;