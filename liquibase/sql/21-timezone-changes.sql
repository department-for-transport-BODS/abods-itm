CREATE INDEX IF NOT EXISTS siri_index_in_group_id  ON public."SiriVMPositions" (group_id);
 
CREATE INDEX IF NOT EXISTS timetable_index_in_group_id  ON public."Timetable" (group_id);

ALTER TABLE public."Timetable" ADD COLUMN IF NOT EXISTS admin_area_id integer;

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
		cast(concat(date_of_journey::text,'' '',departure_time::text) as timestamp) at time zone ''Europe/London'' as departure_time,
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
recorded_at_time::timestamp(0) at TIME zone 'utc', 
response_timestamp::timestamp(0) at TIME zone 'utc', 
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

alter table public.expected_journeys rename column noc_and_line to noc_and_line_and_servicecode;
alter table public.expected_services rename column noc_and_line to noc_and_line_and_servicecode;


-- DROP PROCEDURE public.generate_expected_tables(date);

CREATE OR REPLACE PROCEDURE public.generate_expected_tables(IN partition_date date)
 LANGUAGE plpgsql
AS $procedure$
begin
RAISE NOTICE 'Deleting expected journeys for %', partition_date::text ;

delete from expected_journeys where date_of_journey = partition_date;

RAISE NOTICE 'Inserting expected journeys for for %', partition_date::text ;

insert into expected_journeys (
	date_of_journey,
	operator_noc,
	line_name,
	noc_and_line_and_servicecode,
	journey_code,
	group_id,
	stop_count,
	expected_journey_start,
	journey_pattern_description,
	vehicle_journey_id,
	day_of_week
)
select distinct
	t.date_of_journey,
	t.operator_noc,
	t.line_name,
	concat(t.operator_noc, '-', t.line_name,'-',t.service_code) as noc_and_line_and_servicecode,
	t.journey_code,
	t.group_id,
	count(stop_index) over w as stop_count,
	first_value(t.expected_departure_time) over w as start_time,
	ts.description as journey_pattern_description,
	t.vehiclejourney_id,
	t.day_of_week
from "Timetable" t
left join transmodel_servicepattern ts 
on t.servicepattern_id = ts.id
where t.date_of_journey = partition_date
window w as (
	partition by t.group_id 
	order by t.stop_index asc 
	range between unbounded preceding and unbounded following
)
;

RAISE NOTICE 'Analysing expected journeys for for %', partition_date::text ;

analyse expected_journeys;

RAISE NOTICE 'Deleting expected services for for %', partition_date::text ;

delete from expected_services where date_of_journey = partition_date;

RAISE NOTICE 'Inserting expected services for for %', partition_date::text ;

insert into expected_services (
	date_of_journey,
	operator_noc,
	line_name,
	noc_and_line_and_servicecode,
	service_name
)
select distinct
date_of_journey,
operator_noc,
line_name,
noc_and_line_and_servicecode,
first_value(journey_pattern_description) over (partition by date_of_journey, operator_noc, line_name, noc_and_line_and_servicecode order by stop_count desc, journey_pattern_description asc) as service_name
from expected_journeys
where date_of_journey = partition_date;

RAISE NOTICE 'Analysing expected services for for %', partition_date::text ;

analyse expected_services;

RAISE NOTICE 'Deleting expected operators for for %', partition_date::text ;

delete from expected_operators where date_of_journey = partition_date;

RAISE NOTICE 'Inserting expected operators for for %', partition_date::text ;

insert into expected_operators (
	date_of_journey,
	operator_noc,
	operator_name
)
select distinct es.date_of_journey, es.operator_noc, o."name"
from expected_services es
left join traveline_operators o on
o.noc_code = es.operator_noc
where es.date_of_journey = partition_date;

RAISE NOTICE 'Analysing expected operators for for %', partition_date::text ;

analyse expected_operators;

RAISE NOTICE 'Done';

end; $procedure$
;

alter procedure public.generate_expected_tables owner to abods_rw;

alter table public.expected_journeys alter column expected_journey_start type timestamptz using (date_of_journey + expected_journey_start) at TIME zone 'Europe/London';


CREATE TABLE if not exists public.timetable_threshold_summary (
	threshold_id bigserial NOT NULL,
	operator_noc text NULL,
	line_name text NULL,
	noc_and_line_and_servicecode text NULL,
	service_name text NULL,
	date_of_journey date,
	is_timing_point bool,
	time_diff_minutes float8 NULL,
	departure_hour time, 
	admin_areas int[],
	day_of_week int,
	otp_count int8 NULL
)PARTITION BY RANGE (date_of_journey);


-- DROP PROCEDURE public.create_partition_summary_service();

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
				day_of_week
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
			day_of_week
				
			from 	 
			(	
			select 

			ttb.operator_noc ,
			ttb.line_name ,
			es.noc_and_line_and_servicecode,
			es.service_name,
			case when ttb.time_difference > 0 
				then ceil(ttb.time_difference/60::float)
				else floor(ttb.time_difference/60::float )
			end as time_diff_minutes,
			ttb.date_of_journey,
			ttb.is_timing_point,
			array_agg( ttb.admin_area_id) over (partition by 			ttb.operator_noc ,
			ttb.line_name ,
			ttb.date_of_journey,
			ttb.is_timing_point) array_admin,
			date_trunc(''hour'', ttb.expected_departure_time) AS departure_hour,
			ttb.day_of_week,
			count(*) as otp_count
							

			FROM 
			public."Timetable" ttb
			INNER JOIN public.expected_services es 
				ON ttb.date_of_journey = es.date_of_journey 
				AND ttb.operator_noc = es.operator_noc 
				AND ttb.line_name = es.line_name 
			WHERE  ttb.date_of_journey = %L
			group by 
			ttb.operator_noc ,
			ttb.line_name ,
			es.noc_and_line_and_servicecode,
			es.service_name,
			ttb.date_of_journey,
			ttb.is_timing_point,
			ttb.admin_area_id,
			case when ttb.time_difference > 0 
				then ceil(ttb.time_difference/60::float)
				else floor(ttb.time_difference/60::float )
			end ,
			date_trunc(''hour'', ttb.expected_departure_time),
			ttb.day_of_week
			
			) x ',
				tablename,
				partition_date);
		
		
		-- EXECUTE format(query, tablename, partition_date, partition_date);
	END IF;
	
	partition_date := partition_date + interval '1' day;
-- END LOOP;
END; 
$procedure$
;

select cron.schedule('Refresh create_timetable_threshold_summary', '30 02 * * *',  $$call create_timetable_threshold_summary(now()::date - 1); $$);

alter procedure public.create_timetable_threshold_summary owner to abods_rw;

CREATE INDEX IF NOT EXISTS noc_index_timetable_threshold_summary  ON public.timetable_threshold_summary (date_of_journey,operator_noc);
 
CREATE INDEX IF NOT EXISTS timediff_index_timetable_threshold_summary  ON public.timetable_threshold_summary (date_of_journey,time_diff_minutes);