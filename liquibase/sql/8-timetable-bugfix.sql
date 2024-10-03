CREATE OR REPLACE PROCEDURE public.generate_timetable(IN partition_date date)
 LANGUAGE plpgsql
AS $procedure$

declare 
longdatestring text:= to_char(partition_date, 'YYYY_MM_DD');
timetable_suffix text:= concat('_', longdatestring);
tablename text:= 'Timetable';

begin

RAISE NOTICE '(Re)Creating organisation_timetable temp table';

execute format(
'drop table if exists public.%I', 
concat('organisation_timetable', timetable_suffix)
);

execute format(
'create table public.%I as 
WITH FilteredFiles AS (
		select
		    od.dataset_id,
			a.id as txcfileattributes_id,
	        a.national_operator_code,
	        a.service_code,
	        a.line_names  as line_name,
	        a.filename,
	        a.revision_number,
			a.revision_id,
	        a.operating_period_start_date,
	        a.operating_period_end_date
	    FROM
	        public.organisation_txcfileattributes a
	        join public.organisation_datasetrevision od
			on od.id = a.revision_id
	    where modified > ''2023-06-01''::date 
			and od.is_published is true 
			and od.status = ''live''	
	),
	
	MaxDatasetRevision AS (
	    SELECT
	        dataset_id,
	        --revision_number AS revision_number,
			MAX(revision_id) AS MaxRevisionid
			
	    FROM
	        FilteredFiles
	    GROUP BY
	        dataset_id
	),
	
	QuerydateDatasetRevision as (
	
	select 
			f.dataset_id,
			f.txcfileattributes_id,
	        f.national_operator_code,
	        f.service_code,
	        f.line_name,
	        f.filename,
	        f.revision_number,
			f.revision_id,
	        f.operating_period_start_date,
	        f.operating_period_end_date
	from FilteredFiles f
	
	join MaxDatasetRevision m 
	on f.dataset_id = m.dataset_id
	and f.revision_id=m.MaxRevisionid

	where %L BETWEEN f.operating_period_start_date AND coalesce (f.operating_period_end_date,''2050-12-31''::date)
	),
	MaxFileRevisionNumber as (
		select 
			x.national_operator_code,
			x.service_code,
			x.line_name,
			max(x.revision_number) as max_revision_number
		from QuerydateDatasetRevision x
		group by 
			x.national_operator_code,
			x.service_code,
			x.line_name
	),
	
MaxStartDates as (
		select 
			x.national_operator_code,
			x.service_code,
			x.line_name,
     		max(x.revision_number) as max_revision_number
		from FilteredFiles x
        where x.operating_period_end_date < %L
		group by 
			x.national_operator_code,
			x.service_code,
			x.line_name
	)
	
	 SELECT distinct 
		drv.txcfileattributes_id,
	   drv.national_operator_code,
	  drv.service_code,
	   drv.line_name,
	drv.filename,
	   drv.revision_id,
	drv.revision_number
	
	from 
	
	( SELECT distinct 
		m.txcfileattributes_id,
	    m.national_operator_code,
	    m.service_code,
	    m.line_name,
		m.filename,
	    m.revision_id,
		m.revision_number
	FROM
	    QuerydateDatasetRevision m
	JOIN
	    MaxFileRevisionNumber f
	    ON m.national_operator_code = f.national_operator_code
	    AND m.service_code = f.service_code
	    AND m.line_name = f.line_name
	    AND m.revision_number = f.max_revision_number
	    )  drv 
	    
	 left join MaxStartDates s 
	    ON drv.national_operator_code = s.national_operator_code
	    AND drv.service_code = s.service_code
	    AND drv.line_name = s.line_name
	    and drv.revision_number < s.max_revision_number
	    
	    where s.max_revision_number is null 

	ORDER BY
	    drv.national_operator_code, drv.service_code, drv.line_name
	    ',
concat('organisation_timetable', timetable_suffix),
partition_date,
partition_date
);

RAISE NOTICE '(Re)Creating timetable_vehiclejourney temp table';

execute format(
'drop table if exists public.%I',
concat('timetable_vehiclejourney', timetable_suffix)
);

execute format(
'create table public.%I as 
with vehicle_journey as (
	select 
		a.*,
		tv.*,
		%L::date as date_of_journey,
		ts2.line_name as exploded_line_name
        
    from public.%I a
	join public.transmodel_service ts
	on a.revision_id=ts.revision_id 
	and a.txcfileattributes_id=ts.txcfileattributes_id 
	and %L between ts.start_date and coalesce(ts.end_date,''2050-12-31''::date)
   
   join public.transmodel_service_service_patterns tssp 
   on ts.id =  tssp.service_id 
   
   join public.transmodel_servicepattern ts2 
   on tssp.servicepattern_id =ts2.id
   
   join public.transmodel_vehiclejourney tv 
   on ts2.id = tv.service_pattern_id
   )
   select a.* 
   from vehicle_journey a 
   left join	(SELECT  national_operator_code, exploded_line_name as line_name ,journey_code
FROM vehicle_journey
group by national_operator_code, exploded_line_name,journey_code
having count(distinct service_code) > 1) drv 
on a.national_operator_code = drv.national_operator_code
and a.exploded_line_name = drv.line_name
and a.journey_code = drv.journey_code
where drv.journey_code is null 
   ',
concat('timetable_vehiclejourney', timetable_suffix),
partition_date,
concat('organisation_timetable', timetable_suffix),
partition_date
);

RAISE NOTICE '(Re)Creating timetable_vehiclejourney_workingdays temp table';

execute format (
'drop table if exists public.%I',
concat('timetable_vehiclejourney_workingdays', timetable_suffix)
);

execute format (
'create table public.%I as     
 	select tv.* from 
	public.%I tv 
 	left join (
		select tv.id, 
 		MAX(
			case 
				when %L between tsw.start_date and tsw.end_date and ts.operating_on_working_days is true 
      			then ''yes''
      			when %L not between tsw.start_date and tsw.end_date and ts.operating_on_working_days is false 
      			then ''yes''
      			else ''no''
      		end
		) as flag 
 		from public.%I tv 
 
 		join public.transmodel_servicedorganisationvehiclejourney ts 
 		on tv.id = ts.vehicle_journey_id
 
		join public.transmodel_servicedorganisationworkingdays tsw
		on ts.id  = tsw.serviced_organisation_vehicle_journey_id  
 
		group by tv.id
 	) workingday on 
 
 	tv.id = workingday.id 

	where coalesce(workingday.flag,''yes'') = ''yes''
	',
concat('timetable_vehiclejourney_workingdays', timetable_suffix),
concat('timetable_vehiclejourney', timetable_suffix),
partition_date,
partition_date,
concat('timetable_vehiclejourney', timetable_suffix)
);

RAISE NOTICE '(Re)Creating timetable_vehiclejourney_exclusions temp table';

execute format (
'drop table if exists public.%I',
concat('timetable_vehiclejourney_exclusions', timetable_suffix)
);

execute format (
'create table public.%I as     
		select id from (
			select tvw.id,
			MIN(
				case
					when tne.vehicle_journey_id is not null and toe.operating_date = %L 
         			then 1 -- include 
	   				when top.vehicle_journey_id is not null and  top.day_of_week = to_char(%L::date, ''Day'')
       				then 1 -- include 
       				when tne.vehicle_journey_id is not null and tne.non_operating_date = %L 
       				then 0 -- exclude 
       				else null 
      			end
			) flag 
 		from public.%I tvw 

 		left join public.transmodel_operatingprofile top 
		on tvw.id =top.vehicle_journey_id 

		left join public.transmodel_nonoperatingdatesexceptions tne 
		on tvw.id = tne.vehicle_journey_id

		left join public.transmodel_operatingdatesexceptions toe
		on tvw.id = toe.vehicle_journey_id
 
		group by 1 
 	) x 
 	where x.flag=0',
concat('timetable_vehiclejourney_exclusions', timetable_suffix),
partition_date,
partition_date,
partition_date,
concat('timetable_vehiclejourney_workingdays', timetable_suffix)
);

RAISE NOTICE '(Re)Creating timetable_journey temp table';

execute format (
'drop table if exists public.%I',
concat('timetable_journey', timetable_suffix)
);

execute format (
'create table public.%I as 
 	select 
 		national_operator_code as operator,
		service_code,
		exploded_line_name as line_name,
		'''' as description,
		filename as file_name,
		journey_code,
		date_of_journey,
		extract(dow from date_of_journey) as day_of_week,
		coalesce(stop.naptan_stop_id::text,'''') as stop_id,
		stop.sequence_number  as stop_index,
		stop.departure_time as departure_time,
		stop.is_timing_point as is_timing_point,
		'' '' as group_id,
		tvw.id as transmodel_vehiclejourney_id,
		tvw.service_pattern_id as transmodel_servicepattern_id,
		stop.atco_code
	from public.%I tvw 
	join public.transmodel_servicepatternstop stop 
 	on tvw.id = stop.vehicle_journey_id 
 	where tvw.id not in (
		select id from public.%I
	)
 	and trim(tvw.journey_code) <> ''''
 	',
concat('timetable_journey', timetable_suffix),
concat('timetable_vehiclejourney_workingdays', timetable_suffix),
concat('timetable_vehiclejourney_exclusions', timetable_suffix)
);

RAISE NOTICE '(Re)Creating timetable_stop temp table';

execute format (
'drop table if exists public.%I',
concat('timetable_stop', timetable_suffix)
);

execute format (
'create table public.%I as 
	select 
		"operator" as operator_ref,
		line_name,
		journey_code,
		date_of_journey as date_of_journey,
		departure_time,
		stop_id,
		ST_Y(b.location)::real lt,
		ST_X(b.location)::real as lon,
		common_name as stopname,
		a.stop_index,
		b.common_name as stop_name
		,a.is_timing_point,
		b.locality_id,
		service_code,
		file_name as filename,
		day_of_week,
		stop_type,
		concat("operator",line_name,journey_code,date_of_journey) as group_id,
		a.atco_code,
		row_number() over(partition by "operator",line_name,journey_code,date_of_journey,stop_id order by file_name ) as rk 	
	from public.%I a
	join public.naptan_stoppoint b
	on a.stop_id  = b.id::text
	',
concat('timetable_stop', timetable_suffix),
concat('timetable_journey', timetable_suffix)
);

----------------------------
-- Create dated partition --
----------------------------

RAISE NOTICE '(Re)Creating partition';


execute format(
'CREATE TABLE if not exists public.%I partition of public.%I FOR VALUES FROM (%L) TO (%L)',
concat( tablename, '_p', longdatestring),
tablename,
partition_date,
partition_date + interval '1' day);

execute format('
	ALTER TABLE public.%I OWNER to abods_rw',
	concat( tablename, '_p', longdatestring)
);

------------------------------
-- Deleting from partition --
------------------------------

RAISE NOTICE 'Deleting from partition';

execute format(
	'DELETE FROM public.%I',
	concat( tablename, '_p', longdatestring)
);

----------------------------
-- Importing to partition --
----------------------------

RAISE NOTICE 'Inserting into partition';

execute format(
'Insert into public.%I (
		operator_noc,
		operator_name,
		service_code,
		line_name,
		xml_file_name,
		journey_code,
		date_of_journey,
		day_of_week,
		common_name,
		atco_code,
		stop_type,
		stop_index,
		stop_latitude,
		stop_longitude,
		locality_id,
		expected_departure_time,
		actual_departure_time,
		is_timing_point,
		group_id,
		previous_group_id,
		otp_state,
		expected_headway,
		actual_headway,
		headway_time_difference,
		siri_vm_position_id,
		time_difference,
		stop_id
	)
 
	select 
		operator_ref as operator_noc,
		'''' as operator_name,
		service_code,
		line_name,
		filename as xml_file_name,
		journey_code,
		date_of_journey,
		day_of_week,
		stop_name as common_name,
		atco_code as atco_code,
		stop_type,
		stop_index,
		lt as stop_latitude,
		lon as stop_longitude,
		locality_id,
		departure_time as expected_departure_time,
		null as actual_departure_time,
		is_timing_point,
		group_id as group_id,
		lag(group_id) over(partition by operator_ref,line_name,date_of_journey,stop_id,stop_index  order by stop_id,stop_index, departure_time  asc  )  as previous_group_id,
		null as otp_state,
		cast(extract( epoch from departure_time::time - lag(departure_time::time) over(partition by operator_ref,line_name,date_of_journey,stop_id,stop_index  order by stop_id,stop_index, departure_time  asc  ) )/60 as int) as expected_headway,
		null as actual_headway,
		null as headway_time_difference,
		null as siri_vm_position_id,
		null as time_difference,
		nullif(stop_id,'''')::int

	from public.%I 
	where rk=1 ',
concat( tablename, '_p', longdatestring),
concat('timetable_stop', timetable_suffix),
concat('timetable_vehiclejourney', timetable_suffix)
);

--------------
-- Clean Up --
--------------

RAISE NOTICE 'Cleaning Up';


execute format(
'drop table if exists public.%I', 
concat('organisation_timetable', timetable_suffix)
);

execute format(
'drop table if exists public.%I',
concat('timetable_vehiclejourney', timetable_suffix)
);

execute format (
'drop table if exists public.%I',
concat('timetable_vehiclejourney_workingdays', timetable_suffix)
);

execute format (
'drop table if exists public.%I',
concat('timetable_vehiclejourney_exclusions', timetable_suffix)
);

execute format (
'drop table if exists public.%I',
concat('timetable_journey', timetable_suffix)
);

execute format (
'drop table if exists public.%I',
concat('timetable_stop', timetable_suffix)
);


end; $procedure$
;

alter procedure public.generate_timetable owner to abods_rw;
