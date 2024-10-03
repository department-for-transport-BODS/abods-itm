CREATE OR REPLACE VIEW public.naptan_adminarea_with_shape
AS SELECT na.id,
    na.name,
    na.atco_code,
    st_asgeojson(st_flipcoordinates(nas.shape)) AS st_asgeojson
   FROM naptan_adminarea na
     JOIN naptan_adminarea_shape nas ON na.id = nas.admin_area_id;

ALTER VIEW IF EXISTS public.naptan_adminarea_with_shape owner to abods_proxy_rw;

DO $$
BEGIN
  IF EXISTS(SELECT *
    FROM information_schema.columns
    WHERE table_name='performance_statistics' and column_name='noc_and_line')
  THEN
      ALTER TABLE performance_statistics RENAME COLUMN "noc_and_line" TO "noc_and_line_and_servicecode";
  END IF;
END $$;
ALTER TABLE if exists public.performance_statistics drop constraint if exists performance_statistics_pkey;
ALTER TABLE if exists public.performance_statistics alter column operator_noc drop not null;
ALTER TABLE if exists public.performance_statistics alter column line_name drop not null;
ALTER TABLE if exists public.performance_statistics alter column date_period_start drop not null;
ALTER TABLE if exists public.performance_statistics alter column date_period_end drop not null;
ALTER TABLE if exists public.performance_statistics alter column period_type drop not null;

DO $$
BEGIN
  IF EXISTS(SELECT *
    FROM information_schema.columns
    WHERE table_name='timetable_summary_service' and column_name='noc_and_line')
  THEN
      ALTER TABLE timetable_summary_service RENAME COLUMN "noc_and_line" TO "noc_and_line_and_servicecode";
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS public.timetable_summary_operator_t
(
    timetable_id bigserial,
    operator_noc text COLLATE pg_catalog."default",
    date_of_journey date,
    departure_hour timestamp with time zone,
    departure_hour_only time with time zone,
    day_of_week integer,
    on_time_count integer,
    early_count integer,
    late_count integer,
    completed integer,
    scheduled integer,
    is_timing_point boolean,
    max_early integer,
    max_late integer,
    avg_time_difference numeric,
    admin_areas integer[]
) PARTITION BY RANGE (date_of_journey);

ALTER TABLE IF EXISTS public.timetable_summary_operator_t
    OWNER to abods_proxy_rw;
    
CREATE INDEX IF NOT EXISTS day_of_week_operatort
    ON public.timetable_summary_operator_t USING btree
    (day_of_week ASC NULLS LAST)
;

CREATE INDEX IF NOT EXISTS departure_hour_only_operatort
    ON public.timetable_summary_operator_t USING btree
    (departure_hour_only ASC NULLS LAST)
;

CREATE INDEX IF NOT EXISTS departure_hour_operatort
    ON public.timetable_summary_operator_t USING btree
    (departure_hour ASC NULLS LAST)
;

CREATE INDEX IF NOT EXISTS is_timing_point_operatort
    ON public.timetable_summary_operator_t USING btree
    (is_timing_point ASC NULLS LAST)
;

CREATE INDEX IF NOT EXISTS max_early_operatort
    ON public.timetable_summary_operator_t USING btree
    (max_early ASC NULLS LAST)
;

CREATE INDEX IF NOT EXISTS max_late_operatort
    ON public.timetable_summary_operator_t USING btree
    (max_late ASC NULLS LAST)
;

CREATE INDEX IF NOT EXISTS operator_noc_operatort
    ON public.timetable_summary_operator_t USING btree
    (operator_noc COLLATE pg_catalog."default" ASC NULLS LAST)
;

CREATE TABLE IF NOT EXISTS public.timetable_summary_service_tz
(
    timetable_id bigserial,
    operator_noc text COLLATE pg_catalog."default" NOT NULL,
    line_name text COLLATE pg_catalog."default" NOT NULL,
    noc_and_line_and_servicecode text COLLATE pg_catalog."default" NOT NULL,
    date_of_journey date NOT NULL,
    departure_hour timestamp with time zone NOT NULL,
    departure_hour_only time with time zone NOT NULL,
    day_of_week integer NOT NULL,
    on_time_count integer,
    early_count integer,
    late_count integer,
    completed integer,
    scheduled integer,
    is_timing_point boolean NOT NULL,
    max_early integer NOT NULL,
    max_late integer NOT NULL,
    avg_time_difference numeric,
    admin_areas integer[],
    headway_valid boolean NOT NULL,
    CONSTRAINT timetable_summary_sevice_tz_pkey PRIMARY KEY (operator_noc, date_of_journey, day_of_week, departure_hour, departure_hour_only, is_timing_point, max_early, max_late, line_name, noc_and_line_and_servicecode)
) PARTITION BY RANGE (date_of_journey);

ALTER TABLE IF EXISTS public.timetable_summary_service_tz
    OWNER to abods_proxy_rw;

CREATE INDEX IF NOT EXISTS date_of_journey_servicetz
    ON public.timetable_summary_service_tz USING btree
    (date_of_journey ASC NULLS LAST)
;

CREATE INDEX IF NOT EXISTS day_of_week_servicetz
    ON public.timetable_summary_service_tz USING btree
    (day_of_week ASC NULLS LAST)
;

CREATE INDEX IF NOT EXISTS departure_hour_only_servicetz
    ON public.timetable_summary_service_tz USING btree
    (departure_hour_only ASC NULLS LAST)
;
CREATE INDEX IF NOT EXISTS departure_hour_servicetz
    ON public.timetable_summary_service_tz USING btree
    (departure_hour ASC NULLS LAST)
;

CREATE INDEX IF NOT EXISTS is_timing_point_servicetz
    ON public.timetable_summary_service_tz USING btree
    (is_timing_point ASC NULLS LAST)
;

CREATE INDEX IF NOT EXISTS max_early_servicetz
    ON public.timetable_summary_service_tz USING btree
    (max_early ASC NULLS LAST)
;

CREATE INDEX IF NOT EXISTS max_late_servicetz
    ON public.timetable_summary_service_tz USING btree
    (max_late ASC NULLS LAST)
;

CREATE INDEX IF NOT EXISTS noc_and_line_and_servicecode_servicetz
    ON public.timetable_summary_service_tz USING btree
    (noc_and_line_and_servicecode COLLATE pg_catalog."default" ASC NULLS LAST)
;

CREATE INDEX IF NOT EXISTS operator_noc_servicetz
    ON public.timetable_summary_service_tz USING btree
    (operator_noc COLLATE pg_catalog."default" ASC NULLS LAST)
;

CREATE TABLE IF NOT EXISTS public.timetable_summary_stops_tz
(
    timetable_id bigserial,
    operator_noc text NOT NULL,
    service_code text NOT NULL,
    noc_and_line_and_servicecode text NOT NULL,
    stop_id bigint NOT NULL,
    locality_id text NOT NULL,
    line_name text,
    stop_latitude real NOT NULL,
    stop_longitude real NOT NULL,
    date_of_journey date NOT NULL,
    departure_hour timestamp with time zone NOT NULL,
    departure_hour_only time with time zone NOT NULL,
    day_of_week integer NOT NULL,
    on_time_count integer,
    early_count integer,
    late_count integer,
    completed integer,
    scheduled integer,
    common_name text NOT NULL,
    is_timing_point boolean NOT NULL,
    max_early integer NOT NULL,
    max_late integer NOT NULL,
    avg_time_difference numeric,
    headway_stops_count integer,
    expected_headway numeric,
    actual_headway numeric,
    excess_wait_time numeric,
    CONSTRAINT timetable_summary_stops_tz_pkey PRIMARY KEY (service_code, operator_noc, date_of_journey, day_of_week, departure_hour, departure_hour_only, is_timing_point, max_early, max_late, common_name, stop_id, noc_and_line_and_servicecode, locality_id, stop_latitude, stop_longitude)
) PARTITION BY RANGE (date_of_journey);

ALTER TABLE IF EXISTS public.timetable_summary_stops_tz
    OWNER to abods_proxy_rw;


CREATE INDEX IF NOT EXISTS date_of_journey_stopstz
    ON public.timetable_summary_stops_tz USING btree
    (date_of_journey ASC NULLS LAST)
;


CREATE INDEX IF NOT EXISTS day_of_week_stopstz
    ON public.timetable_summary_stops_tz USING btree
    (day_of_week ASC NULLS LAST)
;


CREATE INDEX IF NOT EXISTS departure_hour_only_stopstz
    ON public.timetable_summary_stops_tz USING btree
    (departure_hour_only ASC NULLS LAST)
;


CREATE INDEX IF NOT EXISTS departure_hour_stopstz
    ON public.timetable_summary_stops_tz USING btree
    (departure_hour ASC NULLS LAST)
;


CREATE INDEX IF NOT EXISTS is_timing_point_stopstz
    ON public.timetable_summary_stops_tz USING btree
    (is_timing_point ASC NULLS LAST)
;


CREATE INDEX IF NOT EXISTS max_early_stopstz
    ON public.timetable_summary_stops_tz USING btree
    (max_early ASC NULLS LAST)
;


CREATE INDEX IF NOT EXISTS max_late_stopstz
    ON public.timetable_summary_stops_tz USING btree
    (max_late ASC NULLS LAST)
;


CREATE INDEX IF NOT EXISTS noc_and_line_and_servicecode_stopstz
    ON public.timetable_summary_stops_tz USING btree
    (noc_and_line_and_servicecode ASC NULLS LAST)
;


CREATE INDEX IF NOT EXISTS operator_noc_stopstz
    ON public.timetable_summary_stops_tz USING btree
    (operator_noc ASC NULLS LAST)
;


CREATE INDEX IF NOT EXISTS service_code_stopstz
    ON public.timetable_summary_stops_tz USING btree
    (service_code ASC NULLS LAST)
;


CREATE INDEX IF NOT EXISTS stop_id_stopstz
    ON public.timetable_summary_stops_tz USING btree
    (stop_id ASC NULLS LAST)
;

CREATE OR REPLACE PROCEDURE public.create_timetable_threshold_summary(
	IN pt_date date)
LANGUAGE 'plpgsql'
AS $BODY$

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
			floor(ttb.time_difference::float/60) as time_diff_minutes,
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
			(
				select operator_noc, 
                     line_name,
					  service_code,
                     case when first_value(stop_id) over( partition by group_id order by group_id,expected_departure_time desc,stop_index  desc  )
                               = stop_id and time_difference < 0 
                           then 0
                           else time_difference
                      end as time_difference,
                     date_of_journey,
                     is_timing_point,
                     expected_departure_time,
                     day_of_week ,
                     admin_area_id,
                     stop_index 

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
			ttb.day_of_week
			
			) x ',
				tablename,
				partition_date,
				partition_date);
		
		
		-- EXECUTE format(query, tablename, partition_date, partition_date);
	END IF;
	
	partition_date := partition_date + interval '1' day;
-- END LOOP;
END; 
$BODY$;
ALTER PROCEDURE public.create_timetable_threshold_summary(date)
    OWNER TO abods_proxy_rw;

DROP PROCEDURE IF EXISTS public.summary_by_operators();
CREATE OR REPLACE PROCEDURE public.summary_by_operators(
	partition_date date default current_date - interval '1 day'
	)
LANGUAGE 'plpgsql'
AS $BODY$

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
        admin_areas
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
        sub.admin_areas
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
                admin_areas
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
        admin_areas',
	tablename,
	partition_date,
	partition_date
);
end; 
$BODY$;
ALTER PROCEDURE public.summary_by_operators
    OWNER TO abods_proxy_rw;

DROP PROCEDURE IF EXISTS public.summary_by_services();
CREATE OR REPLACE PROCEDURE public.summary_by_services(
	partition_date date default current_date - interval '1 day'
	)
LANGUAGE 'plpgsql'
AS $BODY$
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
				headway_valid
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
				END AS headway_valid
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
						ttb.actual_departure_time,
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
						ttb.actual_headway
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
				max_late',
            tablename,
            partition_date,
            partition_date);
		
		-- EXECUTE format(query, tablename, partition_date, partition_date);
	END IF;
	
	partition_date := partition_date + interval '1' day;
-- END LOOP;
END; 
$BODY$;
ALTER PROCEDURE public.summary_by_services
    OWNER TO abods_proxy_rw;

DROP PROCEDURE IF EXISTS public.summary_by_stops();
CREATE OR REPLACE PROCEDURE public.summary_by_stops(
	partition_date date default current_date - interval '1 day')
LANGUAGE 'plpgsql'
AS $BODY$
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
				excess_wait_Time
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
				AVG(sub.headway_time_difference) FILTER (WHERE sub.actual_headway IS NOT NULL) AS excess_wait_Time    
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
					ttb.expected_departure_time ,
					ttb.actual_departure_time,
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
					ttb.headway_time_difference
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
					max_late',
            tablename,
            partition_date,
            partition_date);
		
		-- EXECUTE format(query, tablename, partition_date, partition_date);
	END IF;
	
	partition_date := partition_date + interval '1' day;
-- END LOOP;
END; 
$BODY$;
ALTER PROCEDURE public.summary_by_stops
    OWNER TO abods_proxy_rw;

CREATE OR REPLACE PROCEDURE public.get_date_range(
	IN period_type character varying,
	OUT start_date date,
	OUT end_date date)
LANGUAGE 'plpgsql'
AS $BODY$
BEGIN
	end_date:= CURRENT_DATE - INTERVAL '1 day';

	IF period_type = 'last_7_days' THEN
		start_date:= end_date - INTERVAL '6 days';
		RAISE NOTICE 'last_7_days' ;
	
	ELSEIF period_type = 'last_28_days' THEN
		start_date:= end_date - INTERVAL '27 days';
		RAISE NOTICE 'last_28_days' ;
	
	ELSEIF period_type = 'month_to_date' THEN
		start_date:= DATE_TRUNC('month', end_date);
		RAISE NOTICE 'month_to_date' ;
	
	ELSEIF period_type = 'last_month' THEN
		start_date:= DATE_TRUNC('month', end_date) - INTERVAL '1 month';
		end_date:= DATE_TRUNC('month', end_date) - INTERVAL '1 day';
		RAISE NOTICE 'last_month' ;
	
	ELSE
		start_date:= NULL;
		end_date:= NULL;
	
	END IF;
END;
$BODY$;
ALTER PROCEDURE public.get_date_range(character varying)
    OWNER TO abods_proxy_rw;

CREATE OR REPLACE PROCEDURE public.get_trend_date_range(
	IN period_type character varying,
	OUT start_date date,
	OUT end_date date)
LANGUAGE 'plpgsql'
AS $BODY$
BEGIN
	end_date:= CURRENT_DATE - INTERVAL '1 day';

	IF period_type = 'last_7_days' THEN
		start_date:= end_date - INTERVAL '13 days';
		end_date:= end_date - INTERVAL '7 days';
		RAISE NOTICE 'last_7_days' ;
	
	ELSEIF period_type = 'last_28_days' THEN
		start_date:= end_date - INTERVAL '55 days';
		end_date:= end_date - INTERVAL '28 days';
		RAISE NOTICE 'last_28_days' ;
	
	ELSEIF period_type = 'month_to_date' THEN
		start_date:= DATE_TRUNC('month', end_date - INTERVAL '1 month');
		end_date:= DATE_TRUNC('month', end_date - INTERVAL '1 day');
		RAISE NOTICE 'month_to_date' ;

	ELSEIF period_type = 'last_month' THEN
		start_date:= DATE_TRUNC('month', end_date) - INTERVAL '2 months';
		end_date:= DATE_TRUNC('month', end_date) - INTERVAL '1 month' - INTERVAL '1 day';
		RAISE NOTICE 'last_month' ;
	
	ELSE
		start_date:= NULL;
		end_date:= NULL;
	
	END IF;
END;
$BODY$;
ALTER PROCEDURE public.get_trend_date_range(character varying)
    OWNER TO abods_proxy_rw;

CREATE OR REPLACE PROCEDURE public.update_performance_statistics_v4(
	)
LANGUAGE 'plpgsql'
AS $BODY$

DECLARE
	start_date DATE;
	end_date DATE;
	trend_start_date DATE;
	trend_end_date DATE;
	current_period_stats RECORD;
	trend_period_stats RECORD;
	period_type VARCHAR;
	period_types TEXT[]:= ARRAY['last_7_days', 'last_28_days', 'month_to_date', 'last_month'];
	is_timing_point_var BOOLEAN;
	is_timing_points BOOLEAN[]:= ARRAY[TRUE, FALSE];

BEGIN

	EXECUTE format('DELETE FROM public.performance_statistics');
	RAISE NOTICE 'Deleting the old starts';

	FOREACH period_type IN ARRAY period_types LOOP

		CALL get_date_range(period_type, start_date, end_date);
		CALL get_trend_date_range(period_type, trend_start_date, trend_end_date);

		
		FOREACH is_timing_point_var IN ARRAY is_timing_points LOOP
			RAISE NOTICE 'Timing Point %',  is_timing_point_var;

			EXECUTE format('DROP TABLE IF EXISTS temp_current_stats_%s_%s', period_type, is_timing_point_var);
			EXECUTE format('DROP TABLE IF EXISTS temp_trend_stats_%s_%s', period_type, is_timing_point_var);

	
			-- Create temporary tables for current and trend statistics
		
			EXECUTE format('	
				CREATE TEMP TABLE temp_current_stats_%s_%s AS
					SELECT 
						ttbl.operator_noc,
						ttbl.line_name,
						ttbl.noc_and_line_and_servicecode,
						ttbl.service_name,
						ttbl.is_timing_point,
						ttbl.on_time_count,  
						ttbl.early_count, 
						ttbl.late_count, 
						ttbl.total_count
					FROM (
						SELECT 
							operator_noc,
							line_name,
							noc_and_line_and_servicecode,
							service_name,
							is_timing_point,
							SUM(on_time_count) AS on_time_count,  
							SUM(early_count) AS early_count, 
							SUM(late_count) AS late_count, 
							SUM(on_time_count + early_count + late_count) AS total_count
						FROM public.timetable_summary_service
						WHERE 
							is_timing_point = %L
							AND date_of_journey BETWEEN ''%s'' AND ''%s''
						GROUP BY 
							operator_noc, 
							line_name,
							noc_and_line_and_servicecode,
							service_name,
							is_timing_point
					) AS ttbl;
					', period_type, is_timing_point_var, is_timing_point_var, start_date, end_date);
	
			-- Create temporary tables for current and trend statistics
		
			EXECUTE format('	
				CREATE TEMP TABLE temp_trend_stats_%s_%s AS
					SELECT 
						ttbl.operator_noc,
						ttbl.line_name,
						ttbl.noc_and_line_and_servicecode,
						ttbl.service_name,
						ttbl.is_timing_point,
						ttbl.trend_on_time_count,  
						ttbl.trend_early_count, 
						ttbl.trend_late_count, 
						ttbl.trend_total_count
					FROM (
						SELECT 
							operator_noc,
							line_name,
							noc_and_line_and_servicecode,
							service_name,
							is_timing_point,
							SUM(on_time_count) AS trend_on_time_count,  
							SUM(early_count) AS trend_early_count, 
							SUM(late_count) AS trend_late_count, 
							SUM(on_time_count + early_count + late_count) AS trend_total_count
						FROM public.timetable_summary_service
						WHERE 
							is_timing_point = %L
							AND date_of_journey BETWEEN ''%s'' AND ''%s''
						GROUP BY 
							operator_noc, 
							line_name,
							noc_and_line_and_servicecode,
							service_name,
							is_timing_point
					) AS ttbl;
					', period_type, is_timing_point_var, is_timing_point_var, trend_start_date, trend_end_date);

			--- Calculate performance for current period
	
			EXECUTE format('

				INSERT INTO public.performance_statistics(
					operator_noc,
					line_name,
					noc_and_line_and_servicecode,
		    		service_name,
					is_timing_point,
					date_period_start,
					date_period_end,
					period_type,
					on_time_count,
					early_count,
					late_count,
					total_count,
					on_time_percentage,
					trend_period_start,
					trend_period_end,
					trend_on_time_count,
					trend_early_count,
					trend_late_count,
					trend_total_count,
					trend_percentage,
					percentage_change
				) 
				SELECT 
					c.operator_noc,
					c.line_name,
					c.noc_and_line_and_servicecode,
		    		c.service_name,
					c.is_timing_point,
					''%s'' AS date_period_start,
					''%s'' AS date_period_end,
					''%s'' AS period_type,
					c.on_time_count,
					c.early_count,
					c.late_count,
					c.total_count,
					CASE WHEN c.total_count = 0 THEN 0 ELSE (c.on_time_count::FLOAT / c.total_count)*100 END,
					''%s'' AS trend_period_start,
					''%s'' AS trend_period_end,
					t.trend_on_time_count,
					t.trend_early_count,
					t.trend_late_count,
					t.trend_total_count,
					CASE WHEN t.trend_total_count = 0 THEN 0 ELSE (t.trend_on_time_count::FLOAT / t.trend_total_count)*100 END,
					
					CASE 
					    WHEN c.total_count = 0 AND t.trend_total_count = 0 THEN 0 
					    WHEN c.total_count = 0 THEN -((t.trend_on_time_count::FLOAT / t.trend_total_count)*100)
					    WHEN t.trend_total_count = 0 THEN (c.on_time_count::FLOAT / c.total_count)*100
					    ELSE ((c.on_time_count::FLOAT / c.total_count)*100) - ((t.trend_on_time_count::FLOAT / t.trend_total_count)*100)
					END AS percentage_change
				
				FROM temp_current_stats_%s_%s c
				LEFT JOIN temp_trend_stats_%s_%s t
				ON c.operator_noc = t.operator_noc
				AND c.line_name = t.line_name
				AND c.noc_and_line_and_servicecode = t.noc_and_line_and_servicecode
				AND c.service_name = t.service_name;
				', start_date, end_date, period_type, trend_start_date, trend_end_date, period_type, 
					is_timing_point_var, period_type, is_timing_point_var);	
		END LOOP;
	END LOOP;
END 
$BODY$;
ALTER PROCEDURE public.update_performance_statistics_v4()
    OWNER TO abods_proxy_rw;


alter table if exists expected_services_by_date add column if not exists admin_area_id int4[];
alter table if exists expected_journeys add column if not exists admin_area_id int4[];

drop materialized view if exists public.expected_services;
CREATE MATERIALIZED VIEW public.expected_services
TABLESPACE pg_default
AS SELECT DISTINCT esbd.date_of_journey,
    sd.noc_and_line_and_servicecode,
    sd.operator_noc,
    sd.line_name,
    sd.service_name,
    esbd.admin_area_id
   FROM expected_services_by_date esbd
     LEFT JOIN service_details sd ON esbd.noc_and_line_and_servicecode = sd.noc_and_line_and_servicecode
WITH NO DATA;

alter materialized view public.expected_services owner to abods_proxy_rw;

CREATE INDEX expected_services_date_of_journey_idx ON public.expected_services USING btree (date_of_journey);
CREATE INDEX expected_services_line_name_idx ON public.expected_services USING btree (line_name);
CREATE INDEX expected_services_noc_and_line_and_servicecode_idx ON public.expected_services USING btree (noc_and_line_and_servicecode);
CREATE INDEX expected_services_operator_noc_idx ON public.expected_services USING btree (operator_noc);

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
	admin_area_id
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
		t.admin_area_id
	from "Timetable" t 
	left join transmodel_servicepattern ts 
	on t.servicepattern_id = ts.id
	where t.date_of_journey = partition_date
	window w as (
		partition by t.group_id 
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
	array_agg(admin_area_id) as admin_area_id
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
	day_of_week
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


ALTER PROCEDURE public.generate_expected_tables
    OWNER TO abods_proxy_rw;

SELECT cron.schedule('summary_by_stop', '0 2 * * *', $$CALL public.summary_by_stops();$$);
SELECT cron.schedule('summary_by_services', '20 2 * * *', $$CALL public.summary_by_services();$$);
SELECT cron.schedule('summary_by_operators', '30 2 * * *', $$CALL public.summary_by_operators();$$);

GRANT SELECT ON ALL TABLES IN SCHEMA public TO abods_ro;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO abods_ro;

