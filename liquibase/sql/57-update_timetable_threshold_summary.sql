
CREATE OR REPLACE PROCEDURE public.create_timetable_threshold_summary(IN pt_date date)
 LANGUAGE plpgsql
AS $procedure$

DECLARE
	partition_date date := pt_date;
	tablename text;

BEGIN
	tablename := 'timetable_threshold_summary_' || to_char(partition_date, 'YYYY_MM_DD');

	RAISE NOTICE 'Creating partition if not exists %', tablename;

	IF EXISTS (
		SELECT 1
		FROM public."Timetable"
		WHERE date_of_journey = partition_date
		LIMIT 1
	) THEN
		RAISE NOTICE '(Re)Creating partition';

		EXECUTE format(
			'CREATE TABLE IF NOT EXISTS public.%I PARTITION OF public.timetable_threshold_summary FOR VALUES FROM (%L) TO (%L)',
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
				noc_and_line_and_servicecode,
				service_name,
				time_diff_minutes,
				date_of_journey,
				is_timing_point,
				admin_areas,
				departure_hour,
				otp_count,
				day_of_week,
				estimated
			)
		select
			operator_noc,
			line_name,
			noc_and_line_and_servicecode,
			service_name,
			time_diff_minutes,
			date_of_journey,
			is_timing_point,
			ARRAY(SELECT DISTINCT unnest (array_admin)) as array_admin_area,
			departure_hour,
			otp_count  ,
			day_of_week,
			estimated
			from
			(
			select
			ttb.operator_noc ,
			ttb.line_name ,
			es.noc_and_line_and_servicecode,
			es.service_name,
			floor(ttb.time_difference::float/60) as time_diff_minutes,
			ttb.date_of_journey,
			ttb.is_timing_point,
			array_agg( ttb.admin_area_id) over (partition by 			ttb.operator_noc ,
			ttb.line_name ,
			ttb.date_of_journey,
			ttb.is_timing_point) array_admin,
			date_trunc(''hour'', ttb.expected_departure_time) AS departure_hour,
			ttb.day_of_week,
			count(*) as otp_count,
			estimated
			FROM
			(
				select operator_noc,
                     line_name,
					  service_code,
                     case when first_value(timetable_id) over( partition by group_id, vehiclejourney_id order by group_id,expected_departure_time desc,stop_index  desc  )
                               = timetable_id and time_difference < 0
                           then 0
                           else time_difference
                      end as time_difference,
                     date_of_journey,
                     is_timing_point,
                     expected_departure_time,
                     day_of_week ,
                     admin_area_id,
                     stop_index,
                     (timestamp_after_estimate is not null) AS estimated
              from public."Timetable" where date_of_journey = %L ) ttb
			INNER JOIN public.expected_services es
				ON ttb.date_of_journey = es.date_of_journey
				AND ttb.operator_noc = es.operator_noc
				AND ttb.line_name = es.line_name
				AND ttb.service_code = split_part(
										es.noc_and_line_and_servicecode,
										''-''
										, -1)
			WHERE  ttb.date_of_journey = %L and ttb.time_difference is not null
			group by
			ttb.operator_noc ,
			ttb.line_name ,
			es.noc_and_line_and_servicecode,
			es.service_name,
			ttb.date_of_journey,
			ttb.is_timing_point,
			ttb.admin_area_id,
			floor(ttb.time_difference::float/60),
			date_trunc(''hour'', ttb.expected_departure_time),
			ttb.day_of_week,
			estimated
			) x ',
				tablename,
				partition_date,
				partition_date);


		-- EXECUTE format(query, tablename, partition_date, partition_date);
	END IF;

	partition_date := partition_date + interval '1' day;
-- END LOOP;
END;
$procedure$
;




CREATE OR REPLACE PROCEDURE public.populate_headway(IN pt_date date)
 LANGUAGE plpgsql
AS $procedure$
DECLARE   
	partition_date date := pt_date;
	tablename text;

begin

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
and actual_departure_time is not null
)  x where x.previous_actual_departure_time is not null 
;', partition_date);
		
EXECUTE format(
'
update public."Timetable" y
 
set headway_time_difference = y.expected_headway - x.actual_headway ,
actual_headway = x.actual_headway
from public.temp_timetable_headway x 
where x.timetable_id  = y.timetable_id 
and y.date_of_journey = %L
;', partition_date);

execute format (
' drop table if exists  public.temp_timetable_max_siri_vm_positions_id;'
);



execute format (
'create  table public.temp_timetable_max_siri_vm_positions_id
as 
 select t.timetable_id ,max(sv.siri_vm_positions_id) as max_siri_vm_positions_id  from  public."Timetable" t
 join public."SiriVMPositions" sv 
 on t.operator_noc  = sv.operator_ref 
 and t.line_name = sv.line_name 
 and t.journey_code =sv.journey_ref 
 and t.date_of_journey =sv.date_of_journey 
 and t.actual_departure_time = sv.recorded_at_time
 
 where t.date_of_journey =  %L
 and sv.date_of_journey  =  %L
 group by t.timetable_id

 ;', partition_date,partition_date);
 
execute format (
' 
 update public."Timetable" y
set siri_vm_position_id = x.max_siri_vm_positions_id 
from public.temp_timetable_max_siri_vm_positions_id x 
 where   x.timetable_id  = y.timetable_id 
 and y.date_of_journey = %L
 ;', partition_date);



execute format (
'drop table if exists public.temp_timetable_headway;'
); 

execute format (
' drop table if exists  public.temp_timetable_max_siri_vm_positions_id;'
);

		
END; 
$procedure$
;
