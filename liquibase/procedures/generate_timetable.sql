create or replace procedure generate_timetable(IN partition_date date)
    language plpgsql
as
$$

declare
    longdatestring   text := to_char(partition_date, 'YYYY_MM_DD');
    timetable_suffix text := concat('_', longdatestring);
    tablename        text := 'Timetable';

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

    RAISE NOTICE '(Re)Creating filtered_registered_organisation_timetable table';

    execute format(
            'drop table if exists public.%I',
            concat('filtered_registered_organisation_timetable', timetable_suffix)
            );

    execute format(
            'create table public.%I as
	select *
	from (
		with operator_UZ_group as (
            select txcfileattributes_id, national_operator_code, service_code, line_name, filename, revision_id, revision_number, null as otc_service_code, null as registration_status
            from public.%I
            where service_code like ''UZ%%''
        )
		select ot.txcfileattributes_id, ot.national_operator_code, ot.service_code, ot.line_name, ot.filename, ot.revision_id, ot.revision_number, osn.otc_service_code, osn.registration_status
		from public.%I ot
		join (
	            select os.registration_number, registration_code, concat_ws('':'', substring(os.registration_number, 1, 9), substring(os.registration_number, 11, 12)) as otc_service_code, os.registration_status, os.effective_date
	            from bods.%I os
	            left join bods.%I ois
	            on os.registration_number = ois.registration_number
	            and ois.registration_status = ''Registered''
	            and ois.effective_date = current_date + 1
	            where os.registration_status = ''Registered''
				or os.registration_status = ''''
	            or os.registration_status = ''New''
				or (os.registration_status != ''Registered'' and os.registration_status != '''' and os.effective_date > current_date + 1)
	    ) osn
		on ot.service_code = osn.otc_service_code
		union select * from operator_UZ_group
    )',
            concat('filtered_registered_organisation_timetable', timetable_suffix),
            concat('organisation_timetable', timetable_suffix),
            concat('organisation_timetable', timetable_suffix),
            'otc_service',
            'otc_inactiveservice'
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
            concat('filtered_registered_organisation_timetable', timetable_suffix),
            partition_date
            );


    RAISE NOTICE '(Re)Creating timetable_vehiclejourney_workingdays temp table';

    execute format(
            'drop table if exists public.%I',
            concat('timetable_vehiclejourney_workingdays', timetable_suffix)
            );

    execute format(
            'create table public.%I as
	select tv.* from
	public.%I tv
	left join (
		select tv.id,
			(case when toe.vehicle_journey_id is not null
			then ''yes''
			else max(case when ts.operating_on_working_days is true and tsw.serviced_organisation_vehicle_journey_id is null
      			then ''no''
				when ts.operating_on_working_days is true and tsw.serviced_organisation_vehicle_journey_id is not null
      			then ''yes''
      			when ts.operating_on_working_days is false and tsw.serviced_organisation_vehicle_journey_id is not null
      			then ''no''
      			else ''yes''
      		end )
			end) as flag
		from public.%I tv
		left join (select vehicle_journey_id from public.transmodel_operatingdatesexceptions
		where  %L::date = operating_date) toe
		on tv.id  = toe.vehicle_journey_id
		join public.transmodel_servicedorganisationvehiclejourney ts
		on tv.id = ts.vehicle_journey_id
		left join ( select serviced_organisation_vehicle_journey_id from public.transmodel_servicedorganisationworkingdays
		where  %L::date between start_date and end_date  group by serviced_organisation_vehicle_journey_id ) tsw
		on ts.id  = tsw.serviced_organisation_vehicle_journey_id
		group by tv.id, toe.vehicle_journey_id
	) workingday on
	tv.id = workingday.id
	where coalesce(workingday.flag,''yes'') = ''yes''
	',
            concat('timetable_vehiclejourney_workingdays', timetable_suffix),
            concat('timetable_vehiclejourney', timetable_suffix),
            concat('timetable_vehiclejourney', timetable_suffix),
            partition_date,
            partition_date
            );

    RAISE NOTICE '(Re)Creating timetable_vehiclejourney_exclusions temp table';

    execute format(
            'drop table if exists public.%I',
            concat('timetable_vehiclejourney_exclusions', timetable_suffix)
            );

    execute format(
            'create table public.%I as
		select id from
		(
		select  tvw.id,
		(case when toe.vehicle_journey_id is not null
			then 1
		else MAX(case when top.day_of_week = trim(to_char(%L::date, ''Day''))
		         then 1  -- include
		         else 0  -- exclude
		end)
		end) as flag
		from public.%I tvw
		left join (select vehicle_journey_id from public.transmodel_operatingdatesexceptions
		where  %L::date = operating_date) toe
		on tvw.id  = toe.vehicle_journey_id
		left join public.transmodel_operatingprofile top
		on tvw.id = top.vehicle_journey_id
		group  by tvw.id, toe.vehicle_journey_id
		) oper
		where oper.flag=0;
	',
            concat('timetable_vehiclejourney_exclusions', timetable_suffix),
            partition_date,
            concat('timetable_vehiclejourney_workingdays', timetable_suffix),
            partition_date
            );

    RAISE NOTICE 'Inserting into timetable_vehiclejourney_exclusions temp table';

    execute format(
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
	',
            concat('timetable_vehiclejourney_exclusions', timetable_suffix),
            concat('timetable_vehiclejourney_workingdays', timetable_suffix),
            partition_date,
            concat('timetable_vehiclejourney_exclusions', timetable_suffix),
            partition_date
            );


    RAISE NOTICE '(Re)Creating timetable_journey_workingdays_with_exclusions temp table';

    execute format(
            'drop table if exists public.%I',
            concat('timetable_journey_workingdays_with_exclusions', timetable_suffix)
            );

    execute format(
            'create table public.%I as
select a.* from public.%I a
left join public.%I b
on a.id = b.id
where b.id is null
	',
            concat('timetable_journey_workingdays_with_exclusions', timetable_suffix),
            concat('timetable_vehiclejourney_workingdays', timetable_suffix),
            concat('timetable_vehiclejourney_exclusions', timetable_suffix)
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
            concat('timetable_journey_workingdays_with_exclusions', timetable_suffix)
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
            concat('timetable_journey_workingdays_with_exclusions', timetable_suffix),
            concat('timetable_vehiclejourney_servicecode_dupes', timetable_suffix)
            );

    RAISE NOTICE '(Re)Creating timetable_vj_per_groupid temp table';

    execute format(
            'drop table if exists public.%I',
            concat('timetable_vj_per_groupid', timetable_suffix)
            );

    execute format(
            'create table public.%I as
	with ranked_directional_journeys as (
		select
			row_number() over w as rank,
			count(1) over w as window_size,
			national_operator_code as operator_ref,
			service_code,
			filename,
			exploded_line_name as line_name,
			journey_code,
			date_of_journey,
			direction,
			tvw.id as transmodel_vehiclejourney_id,
			tvw.service_pattern_id as transmodel_servicepattern_id,
			departure_day_shift,
            concat_ws(''|'', national_operator_code,exploded_line_name,journey_code,date_of_journey) as group_id
		from public.%I  tvw
		where trim(tvw.journey_code) <> ''''
		window w as (partition by
			national_operator_code,
			exploded_line_name,
			journey_code,
			date_of_journey,
			direction
			order by id desc,
			service_pattern_id desc
			RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED following
		)
	)
	select
		count(1) over w2 as journey_partition_size,
		*
	from ranked_directional_journeys where rank=1
	window w2 as (partition by
		operator_ref,
		line_name,
		journey_code,
		date_of_journey
		RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED following
	)
	order by count(1) over w2 desc,
	operator_ref,
	line_name,
	journey_code'
        ,
            concat('timetable_vj_per_groupid', timetable_suffix),
            concat('timetable_vehiclejourney_nodupes', timetable_suffix)
            );

    RAISE NOTICE '(Re)Creating timetable_journey temp table';

    execute format(
            'drop table if exists public.%I',
            concat('timetable_journey', timetable_suffix)
            );

    execute format(
            'create table public.%I as
	select
		operator_ref,
		service_code,
		line_name,
		filename as file_name,
		journey_code,
		date_of_journey,
		extract(dow from date_of_journey) as day_of_week,
		coalesce(stop.naptan_stop_id::text,'''') as stop_id,
		stop.sequence_number  as stop_index,
		stop.departure_time as departure_time,
		stop.is_timing_point as is_timing_point,
		group_id,
		transmodel_vehiclejourney_id,
		transmodel_servicepattern_id,
		stop.atco_code,
		direction,
		departure_day_shift
	from public.%I  tvw
	join public.transmodel_servicepatternstop stop
	on tvw.transmodel_vehiclejourney_id = stop.vehicle_journey_id
	where trim(tvw.journey_code) <> ''''
	',
            concat('timetable_journey', timetable_suffix),
            concat('timetable_vj_per_groupid', timetable_suffix)
            );

    RAISE NOTICE '(Re)Creating timetable_stop temp table';

    execute format(
            'drop table if exists public.%I',
            concat('timetable_stop', timetable_suffix)
            );

    execute format(
            'create table public.%I as
	select
		operator_ref,
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
		group_id,
		a.atco_code,
		row_number() over(partition by operator_ref,line_name,journey_code,date_of_journey,stop_id,stop_index order by file_name ) as rk,
		transmodel_servicepattern_id,
		transmodel_vehiclejourney_id as vehiclejourney_id,
		b.admin_area_id,
		direction,
		departure_day_shift
	from public.%I a
	join public.naptan_stoppoint b
	on a.stop_id  = b.id::text
	',
            concat('timetable_stop', timetable_suffix),
            concat('timetable_journey', timetable_suffix)
            );

    -------------------------------
-- Selecting ranked 1 files --
-------------------------------

    RAISE NOTICE 'Selecting rank 1 files';

    execute format(
            'drop table if exists public.%I',
            concat('timetable_stop_rank_1', timetable_suffix)
            );

    execute format(
            'create table public.%I as
	select
		operator_ref as operator_noc,
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
		is_timing_point,
		LOWER(group_id) as group_id,
		null as otp_state,
		null as actual_headway,
		null as headway_time_difference,
		null as siri_vm_position_id,
		null as time_difference,
		nullif(stop_id,'''')::int as stop_id,
		transmodel_servicepattern_id as servicepattern_id,
		vehiclejourney_id,
		admin_area_id,
		row_number() over w as real_index,
		count(*) over w as max_index,
		direction,
		departure_day_shift
	from public.%I
	where rk=1
	window w AS (
    	PARTITION BY group_id, vehiclejourney_id
        ORDER BY departure_time
        RANGE BETWEEN unbounded preceding and unbounded following
            )',
            concat('timetable_stop_rank_1', timetable_suffix),
            concat('timetable_stop', timetable_suffix)
            );

    ----------------------------
--Removing last stop --
----------------------------

    RAISE NOTICE 'Removing last stop';

    execute format(
            'drop table if exists public.%I',
            concat('timetable_stop_no_last_stops', timetable_suffix)
            );

    execute format(
            'create table public.%I as
	select
		operator_noc,
		line_name,
		date_of_journey,
		stop_index,
		expected_departure_time,
		group_id,
		stop_id,
		real_index,
		direction
	from public.%I
	where real_index != max_index',
            concat('timetable_stop_no_last_stops', timetable_suffix),
            concat('timetable_stop_rank_1', timetable_suffix)
            );

    -------------------------------------------------------------
-- Add previous group id for frequent services no last stop--
-------------------------------------------------------------

    RAISE NOTICE 'Adding previous_group_id';

    execute format(
            'drop table if exists public.%I',
            concat('timetable_stop_prev_group_id', timetable_suffix)
            );

    execute format(
            'create table public.%I as
	select
		operator_noc,
		line_name,
		date_of_journey,
		stop_index,
		expected_departure_time,
		group_id,
		CASE
        	WHEN COUNT(*) OVER w >= 6
        	THEN LOWER(LAG(group_id) OVER w)
        ELSE NULL
    	END AS previous_group_id,
		stop_id,
		real_index,
		direction
	from public.%I
		window w AS (
    	PARTITION BY operator_noc, line_name, date_of_journey, stop_id, stop_index, extract(hour from expected_departure_time)
		ORDER BY expected_departure_time, stop_index ASC
        RANGE BETWEEN unbounded preceding and unbounded following
            )',
            concat('timetable_stop_prev_group_id', timetable_suffix),
            concat('timetable_stop_no_last_stops', timetable_suffix)
            );

    ----------------------------
-- Create dated partition --
----------------------------

    RAISE NOTICE '(Re)Creating partition';


    execute format(
            'CREATE TABLE if not exists public.%I partition of public.%I FOR VALUES FROM (%L) TO (%L)',
            concat(tablename, '_p', longdatestring),
            tablename,
            partition_date,
            partition_date + interval '1' day);

    execute format('
	ALTER TABLE public.%I OWNER to abods_rw',
                   concat(tablename, '_p', longdatestring)
            );

    ------------------------------
-- Deleting from partition --
------------------------------

    RAISE NOTICE 'Deleting from partition';

    execute format(
            'DELETE FROM public.%I',
            concat(tablename, '_p', longdatestring)
            );

    --------------------------
--Importing to partition --
--------------------------

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
		admin_area_id,
		direction,
		departure_day_shift
	)
	select
		tsr1.operator_noc,
		'''' as operator_name,
		tsr1.service_code,
		tsr1.line_name,
		tsr1.xml_file_name,
		tsr1.journey_code,
		tsr1.date_of_journey,
		tsr1.day_of_week,
		tsr1.common_name,
		tsr1.atco_code,
		tsr1.stop_type,
		tsr1.stop_index,
		tsr1.stop_latitude,
		tsr1.stop_longitude,
		tsr1.locality_id,
		tsr1.expected_departure_time,
		null as actual_departure_time,
		tsr1.is_timing_point,
		tsr1.group_id,
		LOWER(tspgi.previous_group_id) as previous_group_id,
		tsr1.otp_state,
		extract(epoch from tsr1.expected_departure_time::time - lag(tsr1.expected_departure_time::time) over(partition by tsr1.operator_noc, tsr1.line_name, tsr1.date_of_journey, tsr1.stop_id, tsr1.stop_index order by tsr1.stop_id, tsr1.stop_index, tsr1.expected_departure_time::time asc)) as expected_headway,
		null as actual_headway,
		null as headway_time_difference,
		null as siri_vm_position_id,
		null as time_difference,
		tsr1.stop_id,
		extract( epoch from tsr1.expected_departure_time::time - first_value(tsr1.expected_departure_time::time) over( partition by tsr1.operator_noc,tsr1.line_name,tsr1.journey_code,tsr1.date_of_journey  order by tsr1.stop_index asc) ),
		tsr1.servicepattern_id,
		tsr1.vehiclejourney_id,
		tsr1.admin_area_id,
		tsr1.direction,
		tsr1.departure_day_shift
	from public.%I tsr1
	left join public.%I tspgi
	on tsr1.group_id = tspgi.group_id and tsr1.direction = tspgi.direction and tsr1.real_index = tspgi.real_index
	',
            concat(tablename, '_p', longdatestring),
            concat('timetable_stop_rank_1', timetable_suffix),
            concat('timetable_stop_prev_group_id', timetable_suffix)
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
            concat('filtered_registered_organisation_timetable', timetable_suffix)
            );

    execute format(
            'drop table if exists public.%I',
            concat('timetable_vehiclejourney', timetable_suffix)
            );

    execute format(
            'drop table if exists public.%I',
            concat('timetable_vehiclejourney_workingdays', timetable_suffix)
            );

    execute format(
            'drop table if exists public.%I',
            concat('timetable_vehiclejourney_exclusions', timetable_suffix)
            );

    execute format(
            'drop table if exists public.%I',
            concat('timetable_journey_workingdays_with_exclusions', timetable_suffix)
            );

    execute format(
            'drop table if exists public.%I',
            concat('timetable_vehiclejourney_servicecode_dupes', timetable_suffix)
            );

    execute format(
            'drop table if exists public.%I',
            concat('timetable_vehiclejourney_nodupes', timetable_suffix)
            );

    execute format(
            'drop table if exists public.%I',
            concat('timetable_journey', timetable_suffix)
            );

    execute format(
            'drop table if exists public.%I',
            concat('timetable_stop', timetable_suffix)
            );

    execute format(
            'drop table if exists public.%I',
            concat('timetable_vj_per_groupid', timetable_suffix)
            );

    execute format(
            'drop table if exists public.%I',
            concat('timetable_stop_rank_1', timetable_suffix)
            );

    execute format(
            'drop table if exists public.%I',
            concat('timetable_stop_no_last_stops', timetable_suffix)
            );

    execute format(
            'drop table if exists public.%I',
            concat('timetable_stop_prev_group_id', timetable_suffix)
            );


end;
$$;
