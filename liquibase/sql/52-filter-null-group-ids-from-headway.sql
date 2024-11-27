CREATE OR REPLACE PROCEDURE public.populate_headway(IN pt_date date)
 LANGUAGE plpgsql
AS $procedure$
DECLARE   
	partition_date date := pt_date;
	tablename text;

BEGIN

execute format (
'drop table if exists public.temp_timetable_headway;'
);

EXECUTE format(
'create table public.temp_timetable_headway
as 
select *, extract( epoch from x.actual_departure_time - x.previous_actual_departure_time ) as actual_headway from 
( select 

timetable_id,
actual_departure_time,
lag(actual_departure_time) over(partition by operator_noc,line_name,date_of_journey,stop_id,stop_index  
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