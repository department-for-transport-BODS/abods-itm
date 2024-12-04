alter table timetable_summary_operator_t add column IF NOT EXISTS estimated bool default false;

ALTER TABLE timetable_summary_operator_t
add primary key (operator_noc, date_of_journey, day_of_week, departure_hour, departure_hour_only, is_timing_point, max_early, max_late,avg_time_difference,admin_areas, estimated);


alter table timetable_summary_stops_tz add column IF NOT EXISTS estimated bool default false;

ALTER TABLE timetable_summary_stops_tz DROP CONSTRAINT IF EXISTS timetable_summary_stops_tz_pkey;

ALTER TABLE timetable_summary_stops_tz
add primary key (operator_noc, service_code, noc_and_line_and_servicecode,stop_id,locality_id,line_name,stop_latitude,stop_longitude,date_of_journey, departure_hour,departure_hour_only,day_of_week, common_name, is_timing_point, max_early, max_late, estimated);


alter table timetable_summary_service_tz add column IF NOT EXISTS estimated bool default false;

ALTER TABLE timetable_summary_service_tz DROP CONSTRAINT IF EXISTS timetable_summary_sevice_tz_pkey;

ALTER TABLE timetable_summary_service_tz
add primary key (operator_noc, date_of_journey, day_of_week, departure_hour, departure_hour_only, is_timing_point, max_early, max_late, line_name, noc_and_line_and_servicecode, estimated);


alter table timetable_threshold_summary add column IF NOT EXISTS estimated bool default false;


alter table expected_journeys add column IF NOT EXISTS direction VARCHAR(10);

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
			WHERE  ttb.date_of_journey = %L
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

CREATE OR REPLACE PROCEDURE public.summary_by_operators(IN partition_date date DEFAULT (CURRENT_DATE - '1 day'::interval))
 LANGUAGE plpgsql
AS $procedure$

declare   
	tablename text:= 'timetable_summary_operator_t_' || to_char(partition_date, 'YYYY_MM_DD');

begin
	RAISE NOTICE 'Creating partition if not exists %', tablename;
	RAISE NOTICE '(Re)Creating partition';
	
	execute format(
		'CREATE TABLE if not exists public.%I partition of public.timetable_summary_operator_t FOR VALUES FROM (%L) TO (%L)',
		tablename,
		partition_date,
		partition_date + interval '1' day
	);
	
	execute format('
		ALTER TABLE public.%I OWNER to abods_rw',
		tablename
	);

	------------------------------
	-- Deleting from partition --
	------------------------------
	
	RAISE NOTICE 'Deleting from partition';

	execute format(
		'DELETE FROM public.%I',
		tablename
	);
	
	----- example insert my new data

	execute format(
	'INSERT INTO public.%I (
        operator_noc,
        date_of_journey,
        departure_hour,
        departure_hour_only,
        day_of_week,
        on_time_count, 
        early_count, 
        late_count, 
        completed, 
        scheduled, 
        is_timing_point,
        max_early,
        max_late,
        avg_time_difference,
        admin_areas,
		estimated
    )
    SELECT 
        sub.operator_noc,
        sub.date_of_journey,
        sub.departure_hour,
        sub.departure_hour_only,
        sub.day_of_week,
        SUM(sub.on_time_count) AS on_time_count,  
        SUM(sub.early_count) AS early_count, 
        SUM(sub.late_count) AS late_count, 
        SUM(sub.completed) AS completed,
        SUM(sub.scheduled) AS scheduled,
        sub.is_timing_point,
        sub.max_early,
        sub.max_late,
        sub.avg_time_difference,
        sub.admin_areas,
		sub.estimated
    FROM 
        (
            SELECT 
                operator_noc,
                date_of_journey,
                departure_hour,
                departure_hour_only,
                day_of_week,
                on_time_count,  
                early_count, 
                late_count, 
                completed,
                scheduled,
                is_timing_point,
                max_early,
                max_late,
                avg_time_difference,
                admin_areas,
				estimated
            FROM 
                public.timetable_summary_service_tz
            WHERE 
                date_of_journey = %L
        ) AS sub
    WHERE 
        date_of_journey = %L
    GROUP BY 
        operator_noc, 
        date_of_journey, 
        day_of_week, 
        departure_hour, 
        departure_hour_only,
        is_timing_point, 
        max_early, 
        max_late,
        avg_time_difference,
        admin_areas,
		estimated',
	tablename,
	partition_date,
	partition_date
);
end; 
$procedure$
;

CREATE OR REPLACE PROCEDURE public.summary_by_services(IN partition_date date DEFAULT (CURRENT_DATE - '1 day'::interval))
 LANGUAGE plpgsql
AS $procedure$
DECLARE
	tablename text;

BEGIN
	tablename := 'timetable_summary_service_tz_' || to_char(partition_date, 'YYYY_MM_DD');

	RAISE NOTICE 'Creating partition if not exists %', tablename;

	IF EXISTS (
		SELECT 1
		FROM public."Timetable"
		WHERE date_of_journey = partition_date
		LIMIT 1
	) THEN
		RAISE NOTICE '(Re)Creating partition';

		EXECUTE format(
			'CREATE TABLE IF NOT EXISTS public.%I PARTITION OF public.timetable_summary_service_tz FOR VALUES FROM (%L) TO (%L)',
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
			'INSERT INTO public.%I(
				operator_noc,
				line_name,
				noc_and_line_and_servicecode,
				date_of_journey,
				departure_hour,
				departure_hour_only,
				day_of_week,
				on_time_count,
				early_count,
				late_count,
				completed,
				scheduled,
				is_timing_point,
				max_early,
				max_late,
				avg_time_difference,
				admin_areas,
				headway_valid,
				estimated
			)
			SELECT
				sub.operator_noc,
				sub.line_name,
				sub.noc_and_line_and_servicecode,
				sub.date_of_journey,
				date_trunc(''hour'', sub.expected_departure_time::timestamptz) AS departure_hour,
				(EXTRACT(HOUR FROM sub.expected_departure_time)::text || '':00:00'' ||
					CASE
						WHEN RIGHT(sub.expected_departure_time::text, 6)~ ''^[+-]'' THEN RIGHT(sub.expected_departure_time::text, 6)
						ELSE ''+00''
					END
				)::timetz AS departure_hour_only,
				sub.day_of_week,
				COUNT(CASE WHEN sub.otp_state = ''OnTime'' THEN 1 END) AS on_time_count,
				COUNT(CASE WHEN sub.otp_state = ''Early'' THEN 1 END) AS early_count,
				COUNT(CASE WHEN sub.otp_state = ''Late'' THEN 1 END) AS late_count,
				COUNT(sub.actual_departure_time) AS completed,
				COUNT(*) AS scheduled,
				sub.is_timing_point,
				sub.max_early,
				sub.max_late,
				COALESCE(AVG(sub.avg_time_difference/60.0), 0.0) AS avg_time_difference,
				sub.admin_area_id AS admin_areas,
				CASE
					WHEN COUNT(sub.actual_headway) >=1 THEN TRUE
					ELSE FALSE
				END AS headway_valid,
				sub.estimated
			FROM
				(
					SELECT
						ttb.operator_noc,
						ttb.operator_name,
						es.line_name,
						es.noc_and_line_and_servicecode,
						ttb.date_of_journey,
						ttb.day_of_week,
						ttb.expected_departure_time,
						COALESCE(ttb.actual_departure_time, ttb.timestamp_after_estimate) as actual_departure_time,
						ttb.is_timing_point,
						ttb.otp_state,
						ttb.time_difference,
						ttb.stop_id,
						ttb.stop_latitude,
						ttb.stop_longitude,
						ttb.locality_id,
						CASE
							WHEN otp_state = ''Early'' AND time_difference >= -600 THEN 10
							WHEN otp_state = ''Early'' AND time_difference < -600 AND time_difference >= -1200 THEN 20
							WHEN otp_state = ''Early'' AND time_difference < -1200 AND time_difference >= -1800 THEN 30
							WHEN otp_state = ''Early'' AND time_difference < -1800 AND time_difference >= -2400 THEN 40
							WHEN otp_state = ''Early'' AND time_difference < -2400 AND time_difference >= -3000 THEN 50
							WHEN otp_state = ''Early'' AND time_difference < -3000 AND time_difference >= -3600 THEN 60
							WHEN otp_state = ''Early'' AND time_difference < -3600 THEN 70
							ELSE 0
						END AS max_early,
						CASE
							WHEN otp_state = ''Late'' AND time_difference <= 600 THEN 10
							WHEN otp_state = ''Late'' AND time_difference > 600 AND time_difference <= 1200 THEN 20
							WHEN otp_state = ''Late'' AND time_difference > 1200 AND time_difference <= 1800 THEN 30
							WHEN otp_state = ''Late'' AND time_difference > 1800 AND time_difference <= 2400 THEN 40
							WHEN otp_state = ''Late'' AND time_difference > 2400 AND time_difference <= 3000 THEN 50
							WHEN otp_state = ''Late'' AND time_difference > 3000 AND time_difference <= 3600 THEN 60
							WHEN otp_state = ''Late'' AND time_difference > 3600 THEN 70
							ELSE 0
						END AS max_late,
						time_difference AS avg_time_difference,
						es.admin_area_id,
						ttb.actual_headway,
						(ttb.timestamp_after_estimate is not null) AS estimated,
						ttb.timestamp_after_estimate
					FROM
						public."Timetable" ttb
					INNER JOIN public.expected_services es
						ON ttb.date_of_journey = es.date_of_journey
						AND ttb.operator_noc = es.operator_noc
						AND ttb.line_name = es.line_name
						AND ttb.service_code = split_part(
							es.noc_and_line_and_servicecode,
							''-''
							, -1)
					WHERE
						ttb.date_of_journey = %L
				) AS sub
			WHERE
				date_of_journey = %L
			GROUP BY
				line_name,
				noc_and_line_and_servicecode,
				operator_noc,
				date_of_journey,
				day_of_week,
				departure_hour,
				departure_hour_only,
				is_timing_point,
				max_early,
				admin_area_id,
				max_late,
				estimated',
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

CREATE OR REPLACE PROCEDURE public.summary_by_stops(IN partition_date date DEFAULT (CURRENT_DATE - '1 day'::interval))
 LANGUAGE plpgsql
AS $procedure$
DECLARE   
	tablename text;

BEGIN
	tablename := 'timetable_summary_stops_tz_' || to_char(partition_date, 'YYYY_MM_DD');
	
	RAISE NOTICE 'Creating partition if not exists %', tablename;
	
	IF EXISTS (
		SELECT 1
		FROM public."Timetable"
		WHERE date_of_journey = partition_date
		LIMIT 1
	) THEN
		RAISE NOTICE '(Re)Creating partition';
		
		EXECUTE format(
			'CREATE TABLE IF NOT EXISTS public.%I PARTITION OF public.timetable_summary_stops_tz FOR VALUES FROM (%L) TO (%L)',
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
			'INSERT INTO public.%I(
				operator_noc,
				service_code,
				noc_and_line_and_servicecode,
				stop_id,
				locality_id,
				line_name,
				stop_latitude,
				stop_longitude,
				date_of_journey,
				departure_hour,
				departure_hour_only,
				day_of_week,
				on_time_count, 
				early_count, 
				late_count, 
				completed, 
				scheduled, 
				common_name,
				is_timing_point,
				max_early,
				max_late,
				avg_time_difference,
				headway_stops_count,
				expected_headway,
				actual_headway,
				excess_wait_Time,
				estimated
			)
			SELECT 
				sub.operator_noc,
				sub.service_code,
				sub.noc_and_line_and_servicecode,
				sub.stop_id,
				sub.locality_id,
				sub.line_name,
				sub.stop_latitude,
				sub.stop_longitude,
				sub.date_of_journey,
				date_trunc(''hour'', sub.expected_departure_time::timestamptz) AS departure_hour,
				(EXTRACT(HOUR FROM sub.expected_departure_time)::text || '':00:00'' ||
					CASE 
						WHEN RIGHT(sub.expected_departure_time::text, 6)~ ''^[+-]'' THEN RIGHT(sub.expected_departure_time::text, 6)
						ELSE ''+00''
					END
				)::timetz AS departure_hour_only,
				sub.day_of_week,
				COUNT(CASE WHEN sub.otp_state = ''OnTime'' THEN 1 END) AS on_time_count,  
				COUNT(CASE WHEN sub.otp_state = ''Early'' THEN 1 END) AS early_count, 
				COUNT(CASE WHEN sub.otp_state = ''Late'' THEN 1 END) AS late_count, 
				COUNT(sub.actual_departure_time) AS completed,
				COUNT(*) AS scheduled,
				sub.common_name,
				sub.is_timing_point,
				sub.max_early,
				sub.max_late,
				COALESCE(AVG(sub.avg_time_difference/60.0), 0.0) AS avg_time_difference,
				COUNT(sub.actual_headway) AS headway_stops_count,
				AVG(sub.expected_headway) AS expected_headway,
				AVG(sub.actual_headway) FILTER (WHERE sub.actual_headway IS NOT NULL) AS actual_headway,
				AVG(sub.headway_time_difference) FILTER (WHERE sub.actual_headway IS NOT NULL) AS excess_wait_Time,
				sub.estimated   
			FROM 
				(
					SELECT 
					ttb.operator_noc,
					ttb.service_code,
					es.noc_and_line_and_servicecode,
					ttb.stop_id,
					ttb.locality_id,
					ttb.line_name,
					ttb.date_of_journey,
					ttb.day_of_week,
					ttb.common_name,
					ttb.expected_departure_time,
					COALESCE(ttb.actual_departure_time, ttb.timestamp_after_estimate) as actual_departure_time,
					ttb.is_timing_point,
					ttb.otp_state,
					ttb.time_difference,
					ttb.stop_latitude,
					ttb.stop_longitude,
					CASE 
						WHEN otp_state = ''Early'' AND time_difference >= -600 THEN 10
						WHEN otp_state = ''Early'' AND time_difference < -600 AND time_difference >= -1200 THEN 20
						WHEN otp_state = ''Early'' AND time_difference < -1200 AND time_difference >= -1800 THEN 30
						WHEN otp_state = ''Early'' AND time_difference < -1800 AND time_difference >= -2400 THEN 40
						WHEN otp_state = ''Early'' AND time_difference < -2400 AND time_difference >= -3000 THEN 50
						WHEN otp_state = ''Early'' AND time_difference < -3000 AND time_difference >= -3600 THEN 60
						WHEN otp_state = ''Early'' AND time_difference < -3600 THEN 70
						ELSE 0
					END AS max_early,
					CASE 
						WHEN otp_state = ''Late'' AND time_difference <= 600 THEN 10
						WHEN otp_state = ''Late'' AND time_difference > 600 AND time_difference <= 1200 THEN 20
						WHEN otp_state = ''Late'' AND time_difference > 1200 AND time_difference <= 1800 THEN 30
						WHEN otp_state = ''Late'' AND time_difference > 1800 AND time_difference <= 2400 THEN 40
						WHEN otp_state = ''Late'' AND time_difference > 2400 AND time_difference <= 3000 THEN 50
						WHEN otp_state = ''Late'' AND time_difference > 3000 AND time_difference <= 3600 THEN 60
						WHEN otp_state = ''Late'' AND time_difference > 3600 THEN 70
						ELSE 0
					END AS max_late,
					ttb.time_difference AS avg_time_difference,
					ttb.expected_headway,
					ttb.actual_headway,
					ttb.headway_time_difference,
					(ttb.timestamp_after_estimate is not null) AS estimated
				FROM 
					public."Timetable" ttb
					INNER JOIN public.expected_services es 
						ON ttb.date_of_journey = es.date_of_journey 
						AND ttb.operator_noc = es.operator_noc 
						AND ttb.line_name = es.line_name 
						AND ttb.service_code = split_part(
							es.noc_and_line_and_servicecode,
							''-''
							, -1)
					WHERE 
						ttb.date_of_journey = %L
				) AS sub
				WHERE 
					date_of_journey = %L
				GROUP BY 
					operator_noc, 
					service_code, 
					noc_and_line_and_servicecode,
					stop_id,
					locality_id,
					line_name,
					stop_latitude,
					stop_longitude,
					date_of_journey, 
					departure_hour,
					departure_hour_only,
					day_of_week, 
					common_name, 
					is_timing_point, 
					max_early, 
					max_late,
					estimated',
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
	day_of_week,
	admin_area_id,
	expected_journey_end,
	direction
)
with journeys as (
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
		t.day_of_week,
		t.admin_area_id,
		last_value(t.expected_departure_time) over w as end_time,
		t.direction
	from "Timetable" t
	left join transmodel_servicepattern ts
	on t.servicepattern_id = ts.id
	where t.date_of_journey = partition_date
	window w as (
		partition by t.group_id, t.vehiclejourney_id
		order by t.stop_index asc
		range between unbounded preceding and unbounded following
	)
)
select
	date_of_journey,
	operator_noc,
	line_name,
	noc_and_line_and_servicecode,
	journey_code,
	group_id,
	stop_count,
	start_time,
	journey_pattern_description,
	vehiclejourney_id,
	day_of_week,
	array_agg(admin_area_id) as admin_area_id,
	end_time,
	direction
from journeys
group by
	date_of_journey,
	operator_noc,
	line_name,
	noc_and_line_and_servicecode,
	journey_code,
	group_id,
	stop_count,
	start_time,
	journey_pattern_description,
	vehiclejourney_id,
	day_of_week,
	end_time,
	direction
;
 
RAISE NOTICE 'Analysing expected journeys for for %', partition_date::text ;
 
analyse expected_journeys;
 
RAISE NOTICE 'Deleting expected_services_by_date for for %', partition_date::text ;
 
delete from expected_services_by_date where date_of_journey = partition_date;
 
RAISE NOTICE 'Inserting expected_services_by_date for for %', partition_date::text ;
 
insert into expected_services_by_date (
	date_of_journey,
	noc_and_line_and_servicecode,
	admin_area_id
)
select
date_of_journey,
noc_and_line_and_servicecode,
array_agg(admin_area_id) as admin_area_id
from (
select distinct
date_of_journey,
noc_and_line_and_servicecode,
unnest(admin_area_id) as admin_area_id
from expected_journeys
where date_of_journey = partition_date)
group by
date_of_journey,
noc_and_line_and_servicecode;
 
RAISE NOTICE 'Analysing expected_services_by_date  for %', partition_date::text ;
 
analyse expected_services_by_date;
 
RAISE NOTICE 'Upserting service_details for %', partition_date::text ;
 
insert into service_details (
noc_and_line_and_servicecode,
operator_noc,
line_name,
service_name
)
select distinct
noc_and_line_and_servicecode,
operator_noc,
line_name,
first_value(journey_pattern_description) over (partition by date_of_journey, operator_noc, line_name, noc_and_line_and_servicecode order by stop_count desc, journey_pattern_description asc) as service_name
from expected_journeys
where date_of_journey = partition_date
on conflict (noc_and_line_and_servicecode)
do update set (
operator_noc,
line_name,
service_name
) = (
EXCLUDED.operator_noc,
EXCLUDED.line_name,
EXCLUDED.service_name
);
 
RAISE NOTICE 'Analysing service_details for for %', partition_date::text ;
 
analyse service_details;
 
RAISE NOTICE 'Refreshing expected_services for for %', partition_date::text ;
 
refresh materialized view expected_services;
 
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
 
