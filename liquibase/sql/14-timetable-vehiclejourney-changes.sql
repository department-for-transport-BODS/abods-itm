ALTER TABLE public."Timetable" ALTER COLUMN journey_pattern TYPE integer USING (journey_pattern[1]) ;

ALTER TABLE public."Timetable" RENAME COLUMN  journey_pattern TO servicepattern_id;

ALTER TABLE  public."Timetable" ADD column if not exists vehiclejourney_id integer NULL;

ALTER TABLE public."SiriVMPositions"ADD COLUMN IF NOT EXISTS group_id text;

ALTER TABLE public."Timetable" ADD COLUMN IF NOT EXISTS recorded_at_time_utc timestamp;

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

			inner join public.organisation_dataset d 
			on d.live_revision_id= a.revision_id

	    where 
            --od.modified > ''2023-06-01''::date  and 
			 od.is_published is true 
			and od.status = ''live''
			and d.dataset_type = 1	
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

	where %L BETWEEN f.operating_period_start_date AND coalesce (f.operating_period_end_date,''2050-12-31''::date)
	),
	MaxFileRevisionNumber as (
		select 
			x.national_operator_code,
			x.service_code,
			--x.line_name,
			max(x.revision_number) as max_revision_number
		from QuerydateDatasetRevision x
		group by 
			x.national_operator_code,
			x.service_code
			--x.line_name
	),
	
MaxStartDates as (
		select 
			x.national_operator_code,
			x.service_code,
			--x.line_name,
     		max(x.revision_number) as max_revision_number
		from FilteredFiles x
        where x.operating_period_end_date < %L
		group by 
			x.national_operator_code,
			x.service_code
			--x.line_name
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
	    --AND m.line_name = f.line_name
	    AND m.revision_number = f.max_revision_number
	    )  drv 
	    
	 left join MaxStartDates s 
	    ON drv.national_operator_code = s.national_operator_code
	    AND drv.service_code = s.service_code
	    --AND drv.line_name = s.line_name
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
   ',
concat('timetable_vehiclejourney', timetable_suffix),
partition_date,
concat('organisation_timetable', timetable_suffix),
partition_date
);

RAISE NOTICE '(Re)Creating timetable_vehiclejourney_servicecode_dupes temp table';

execute format(
'drop table if exists public.%I',
concat('timetable_vehiclejourney_servicecode_dupes', timetable_suffix)
);

execute format(
'create table public.%I as 
SELECT  national_operator_code, exploded_line_name as line_name ,journey_code
FROM public.%I
group by national_operator_code, exploded_line_name,journey_code
having count(distinct service_code) > 1
   ',
concat('timetable_vehiclejourney_servicecode_dupes', timetable_suffix),
concat('timetable_vehiclejourney', timetable_suffix)
);

RAISE NOTICE '(Re)Creating timetable_vehiclejourney_nodupes temp table';

execute format(
'drop table if exists public.%I',
concat('timetable_vehiclejourney_nodupes', timetable_suffix)
);

execute format(
'create table public.%I as 
   select a.* 
   from public.%I a 
   left join public.%I drv 
on a.national_operator_code = drv.national_operator_code
and a.exploded_line_name = drv.line_name
and a.journey_code = drv.journey_code
where drv.journey_code is null 
   ',
concat('timetable_vehiclejourney_nodupes', timetable_suffix),
concat('timetable_vehiclejourney', timetable_suffix),
concat('timetable_vehiclejourney_servicecode_dupes', timetable_suffix)
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
			max(case when ts.operating_on_working_days is true and tsw.serviced_organisation_vehicle_journey_id is null 
      			then ''no''
				when ts.operating_on_working_days is true and tsw.serviced_organisation_vehicle_journey_id is not null 
      			then ''yes''
      			when ts.operating_on_working_days is false and tsw.serviced_organisation_vehicle_journey_id is not null 
      			then ''no''
      			else ''yes''
      		end ) as flag 
 		from public.%I tv 
 
 		join public.transmodel_servicedorganisationvehiclejourney ts 
 		on tv.id = ts.vehicle_journey_id
 
 		left join ( select serviced_organisation_vehicle_journey_id from public.transmodel_servicedorganisationworkingdays 
		where  %L::date between start_date and end_date  group by serviced_organisation_vehicle_journey_id ) tsw
		on ts.id  = tsw.serviced_organisation_vehicle_journey_id 
 
		group by tv.id
 	) workingday on 
 
 	tv.id = workingday.id 

	where coalesce(workingday.flag,''yes'') = ''yes''
	',
concat('timetable_vehiclejourney_workingdays', timetable_suffix),
concat('timetable_vehiclejourney_nodupes', timetable_suffix),
concat('timetable_vehiclejourney_nodupes', timetable_suffix),
partition_date
);

RAISE NOTICE '(Re)Creating timetable_vehiclejourney_exclusions temp table';

execute format (
'drop table if exists public.%I',
concat('timetable_vehiclejourney_exclusions', timetable_suffix)
);

execute format (
'create table public.%I as     
		select id from 
		(
		select  tvw.id,
		MAX(case when top.day_of_week = trim(to_char(%L::date, ''Day'')) 
		         then 1  -- include 
		         else 0  -- exclude
		end) as flag 
 		from public.%I tvw 

 		join public.transmodel_operatingprofile top 
		on tvw.id =top.vehicle_journey_id 
		group  by tvw.id
		) oper 
		
		where oper.flag=0;
	',
concat('timetable_vehiclejourney_exclusions', timetable_suffix),
partition_date,
concat('timetable_vehiclejourney_workingdays', timetable_suffix)
);

RAISE NOTICE 'Inserting into timetable_vehiclejourney_exclusions temp table';

execute format (
'insert into public.%I
		(id
		)
	  select 
	   tvw.id
	  
	  from public.%I tvw 
		
	  join public.transmodel_nonoperatingdatesexceptions tne 
	  on tvw.id = tne.vehicle_journey_id
	  
	  where tne.non_operating_date = %L::date
	  
	  group by 1
	  ;
	delete from public.%I where id in (select id from public.transmodel_operatingdatesexceptions where operating_date =  %L::date );
	',
concat('timetable_vehiclejourney_exclusions', timetable_suffix),
concat('timetable_vehiclejourney_workingdays', timetable_suffix),
partition_date,
concat('timetable_vehiclejourney_exclusions', timetable_suffix),
partition_date
);


RAISE NOTICE '(Re)Creating timetable_vehiclejourney_workingdays_with_exclusions temp table';

execute format (
'drop table if exists public.%I',
concat('timetable_vehiclejourney_workingdays_with_exclusions', timetable_suffix)
);

execute format (
'create table public.%I as 
 select a.* from public.%I a 
 left join public.%I b 
 on a.id = b.id 
 where b.id is null 
 	',
concat('timetable_vehiclejourney_workingdays_with_exclusions', timetable_suffix),
concat('timetable_vehiclejourney_workingdays', timetable_suffix),
concat('timetable_vehiclejourney_exclusions', timetable_suffix)
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

	from public.%I  tvw

	join public.transmodel_servicepatternstop stop 
 	on tvw.id = stop.vehicle_journey_id 

 	where trim(tvw.journey_code) <> ''''
 	',
concat('timetable_journey', timetable_suffix),
concat('timetable_vehiclejourney_workingdays_with_exclusions', timetable_suffix)
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
		row_number() over(partition by "operator",line_name,journey_code,date_of_journey,stop_id order by file_name ) as rk,
		transmodel_servicepattern_id,
		transmodel_vehiclejourney_id as vehiclejourney_id,
		b.admin_area_id
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
		stop_id,
		off_set,
		servicepattern_id,
		vehiclejourney_id,
		admin_area_id
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
		nullif(stop_id,'''')::int,
		extract( epoch from departure_time::time - first_value(departure_time::time) over( partition by operator_ref,line_name,journey_code,date_of_journey  order by stop_index asc) ),
		transmodel_servicepattern_id,
		vehiclejourney_id,
		admin_area_id

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


-- DROP FUNCTION public.load_avl_tables(int4);

CREATE OR REPLACE FUNCTION public.load_avl_tables(input_batch_id integer)
 RETURNS boolean
 LANGUAGE plpgsql
AS $function$
begin


INSERT INTO public."SiriVMPositions"
(operator_ref,line_name,journey_ref,date_of_journey, direction_ref,recorded_at_time, response_time_stamp, Latitude, Longitude, vehicle_ref, batch_id, group_id)

select 
operator_ref,
coalesce(line_name,''),
journey_ref,
date_of_journey, 
direction_ref,
recorded_at_time::timestamp(0), 
response_timestamp::timestamp(0), 
latitude::real,
longitude::real,
vehicle_ref,
batch_id,
concat(operator_ref,coalesce(line_name,''),journey_ref,to_char(date_of_journey,'YYYY-MM-DD') ) as group_id

from public.staging_avl_positions pos 

where batch_id=input_batch_id
and date_of_journey = now()::date 
ON CONFLICT DO NOTHING
;

delete from public.staging_avl_positions where batch_id =  input_batch_id;

RETURN true;

END;$function$
;


alter function public.load_avl_tables owner to abods_rw;

CREATE INDEX IF NOT EXISTS siri_index_in_group_id  ON public."SiriVMPositions" (group_id);
 
CREATE INDEX IF NOT EXISTS timetable_index_in_group_id  ON public."Timetable" (group_id);

ALTER TABLE public."Timetable" ADD COLUMN IF NOT EXISTS admin_area_id integer;