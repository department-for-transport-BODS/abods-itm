-- Generate timetables daily after 6pm (5pm UTC)

CREATE OR REPLACE PROCEDURE public.update_all_transmodel_tables()
 LANGUAGE plpgsql
AS $procedure$
begin
raise notice 'Running update_transmodel_servicepattern at %', current_timestamp;
call public.update_transmodel_servicepattern();
raise notice 'Running update_transmodel_servicepatternstop at %', current_timestamp;
call public.update_transmodel_servicepatternstop();
raise notice 'Running update_organisation_datasetrevision at %', current_timestamp;
call public.update_organisation_datasetrevision();
raise notice 'Running update_organisation_txcfileattributes at %', current_timestamp;
call public.update_organisation_txcfileattributes();
raise notice 'Running update_transmodel_nonoperatingdatesexceptions at %', current_timestamp;
call public.update_transmodel_nonoperatingdatesexceptions();
raise notice 'Running update_transmodel_operatingdatesexceptions at %', current_timestamp;
call public.update_transmodel_operatingdatesexceptions();
raise notice 'Running update_transmodel_operatingprofile at %', current_timestamp;
call public.update_transmodel_operatingprofile();
raise notice 'Running update_transmodel_service at %', current_timestamp;
call public.update_transmodel_service();
raise notice 'Running update_transmodel_service_service_patterns at %', current_timestamp;
call public.update_transmodel_service_service_patterns();
raise notice 'Running update_transmodel_servicedorganisationvehiclejourney at %', current_timestamp;
call public.update_transmodel_servicedorganisationvehiclejourney();
raise notice 'Running update_transmodel_servicedorganisationworkingdays at %', current_timestamp;
call public.update_transmodel_servicedorganisationworkingdays();
raise notice 'Running update_transmodel_vehiclejourney at %', current_timestamp;
call public.update_transmodel_vehiclejourney();
end; $procedure$
;

alter procedure public.update_all_transmodel_tables owner to abods_rw;

CREATE OR REPLACE PROCEDURE public.update_all_naptan_tables()
 LANGUAGE plpgsql
AS $procedure$
begin
raise notice 'Running update_naptan_adminarea at %', current_timestamp;
call public.update_naptan_adminarea();
raise notice 'Running update_naptan_locality at %', current_timestamp;
call public.update_naptan_locality();
raise notice 'Running update_naptan_stoppoint at %', current_timestamp;
call public.update_naptan_stoppoint();
end; $procedure$
;

alter procedure public.update_all_naptan_tables owner to abods_rw;

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
		SELECT
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
	    WHERE
			%L BETWEEN operating_period_start_date AND coalesce (operating_period_end_date,''2050-12-31''::date)
	        and modified > ''2023-06-01''::date 
			and od.is_published is true 
			and od.status = ''live''	
	),
	
	MaxRevisionFiles AS (
	    SELECT
	        national_operator_code,
	        service_code,
	        line_name,
	        --revision_number AS revision_number,
			MAX(revision_id) AS MaxRevisionid
			
	    FROM
	        FilteredFiles
	    GROUP BY
	        national_operator_code, service_code, line_name
	),
	MaxStartDates as (
		select 
			x.national_operator_code,
			x.service_code,
			x.line_names,
			max(x.operating_period_start_date) as max_date
		from organisation_txcfileattributes x
			    where x.operating_period_start_date > %L
		group by 
			x.national_operator_code,
			x.service_code,
			x.line_names

	)
	
	SELECT distinct 
		f.txcfileattributes_id,
	    f.national_operator_code,
	    f.service_code,
	    f.line_name,
		f.filename,
	    f.revision_id,
		f.revision_number
	FROM
	    MaxRevisionFiles m
	JOIN
	    FilteredFiles f
	    ON m.national_operator_code = f.national_operator_code
	    AND m.service_code = f.service_code
	    AND m.line_name = f.line_name
	    AND m.MaxRevisionid = f.revision_id
	left join MaxStartDates msd
		on f.national_operator_code = msd.national_operator_code
		and f.service_code = msd.service_code
		and f.line_name = msd.line_names
	WHERE
	    msd.max_date is null
	ORDER BY
	    f.national_operator_code, f.service_code, f.line_name',
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
   on ts2.id = tv.service_pattern_id',
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
				when current_date between tsw.start_date and tsw.end_date and ts.operating_on_working_days is true 
      			then ''yes''
      			when current_date not between tsw.start_date and tsw.end_date and ts.operating_on_working_days is false 
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
					when tne.vehicle_journey_id is not null and toe.operating_date = current_date 
         			then 1 -- include 
	   				when top.vehicle_journey_id is not null and  top.day_of_week = to_char(now(), ''Day'')
       				then 1 -- include 
       				when tne.vehicle_journey_id is not null and tne.non_operating_date = current_date 
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

	from public.%I x 

	where rk=1',
concat( tablename, '_p', longdatestring),
concat('timetable_stop', timetable_suffix)
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


-- Update organisation_organisation foreign table and all downstream to take advantage of new supergroup tag

alter foreign table bods.organisation_organisation add column if not exists is_abods_global_viewer bool;

CREATE OR REPLACE VIEW public.bods_organisation
AS WITH all_orgs AS (
         SELECT oo.id,
            oo.name,
            oo.is_abods_global_viewer
           FROM bods.organisation_organisation oo
             LEFT JOIN bods.organisation_operatorcode oo2 ON oo.id = oo2.organisation_id
          WHERE oo2.noc IS NOT NULL OR oo.is_abods_global_viewer = true
        )
 SELECT id,
    name,
    bool_or(is_abods_global_viewer) AS is_abods_global_viewer
   FROM all_orgs
  GROUP BY id, name;

alter view public.bods_organisation owner to abods_rw;