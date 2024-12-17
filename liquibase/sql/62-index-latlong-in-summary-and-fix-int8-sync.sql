create index if not exists timetable_summary_stops_tz_longitude_idx on timetable_summary_stops_tz using BTREE (stop_longitude);
create index if not exists timetable_summary_stops_tz_latitude_idx on timetable_summary_stops_tz using BTREE (stop_latitude);

CREATE OR REPLACE PROCEDURE public.update_transmodel_servicepatternstop()
 LANGUAGE plpgsql
AS $procedure$
declare 
max_current int8:= coalesce((select max(id) from public.transmodel_servicepatternstop), 0);
begin
insert into public.transmodel_servicepatternstop (
	id,
	sequence_number,
	atco_code,
	naptan_stop_id,
	service_pattern_id,
	departure_time,
	is_timing_point,
	txc_common_name,
	vehicle_journey_id,
	stop_activity_id
)
select
	id,
	sequence_number,
	atco_code,
	naptan_stop_id,
	service_pattern_id,
	departure_time,
	is_timing_point,
	txc_common_name,
	vehicle_journey_id,
	stop_activity_id
 from bods.transmodel_servicepatternstop ts
where ts.id > max_current
on conflict do nothing;
end; $procedure$
;
