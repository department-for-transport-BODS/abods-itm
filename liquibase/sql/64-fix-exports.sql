CREATE OR REPLACE PROCEDURE public.historic_timetable_export(IN partition_date DATE)
    LANGUAGE PLPGSQL AS
$procedure$
DECLARE
    datestring TEXT := to_char(partition_date, 'YYYY-MM-DD');
BEGIN
    RAISE NOTICE 'Exporting timetable for date %', partition_date::TEXT;

    PERFORM (SELECT COUNT(*)
             FROM aws_s3.query_export_to_s3(
                     format('
                        SELECT group_id,
                               stop_index,
                               stop_latitude,
                               stop_longitude,
                               expected_departure_time::TIME AS expected_departure_time,
                               timetable_id,
                               date_of_journey,
                               direction,
                               operator_noc
                        FROM public."Timetable"
                        WHERE date_of_journey = ''%s''::DATE
                        ORDER BY group_id ASC,
                                 direction ASC,
                                 stop_index ASC
                            ', datestring),
                     aws_commons.create_s3_uri(
                             concat('abods-', SPLIT_PART(aurora_db_instance_identifier(), '-', 2), '-exporter-bucket'),
                             concat(
                                     'historic/csv/timetable/YYYY=',
                                     DATE_PART('year', partition_date),
                                     '/MM=',
                                     DATE_PART('month', partition_date),
                                     '/',
                                     datestring,
                                     '.csv'
                             ),
                             'eu-west-2'
                     ),
                     options := 'format csv'
                  ));

    RAISE NOTICE 'Exported timetable for date %', partition_date::TEXT;
END;
$procedure$;


CREATE OR REPLACE PROCEDURE public.historic_avl_export(IN partition_date DATE)
    LANGUAGE PLPGSQL AS
$procedure$
DECLARE
    datestring TEXT := to_char(partition_date, 'YYYY-MM-DD');
BEGIN
    RAISE NOTICE 'Exporting sirivmpositions for date %', partition_date::TEXT;

    PERFORM (SELECT COUNT(*)
             FROM aws_s3.query_export_to_s3(
                     format('SELECT
                                operator_ref,
                                line_name,
                                journey_ref,
                                direction_ref,
                                date_of_journey,
                                latitude,
                                longitude,
                                vehicle_ref,
                                recorded_at_time,
                                response_time_stamp,
                                lower(concat_ws(''|'', operator_ref, line_name, journey_ref, date_of_journey)) as group_id,
                                origin_ref,
                                destination_ref,
                                departure_time
                             FROM public."SiriVMPositions"
                             WHERE date_of_journey = ''%s''::DATE', datestring),
                     aws_commons.create_s3_uri(
                             concat('abods-', SPLIT_PART(aurora_db_instance_identifier(), '-', 2), '-exporter-bucket'),
                             concat(
                                     'historic/csv/siri/YYYY=',
                                     DATE_PART('year', partition_date),
                                     '/MM=',
                                     DATE_PART('month', partition_date),
                                     '/siri_vm_',
                                     datestring,
                                     '.csv'
                             ),
                             'eu-west-2'),
                     options := 'format csv'
                  ));

    RAISE NOTICE 'Exported sirivmpositions for date %', partition_date::TEXT;
END;
$procedure$;


CREATE OR REPLACE PROCEDURE public.historic_matching_summary_generation(IN partition_date DATE)
    LANGUAGE plpgsql
AS
$$
BEGIN
    RAISE NOTICE '----------------Calling generate_expected_tables----------------';
    CALL public.generate_expected_tables(partition_date);

    RAISE NOTICE '----------------Calling create_timetable_threshold_summary----------------';
    CALL public.create_timetable_threshold_summary(partition_date);

    RAISE NOTICE '----------------Calling populate_headway----------------';
    CALL public.populate_headway(partition_date);

    RAISE NOTICE '----------------Calling summary_by_stops----------------';
    CALL public.summary_by_stops(partition_date);

    RAISE NOTICE '----------------Calling summary_by_services----------------';
    CALL public.summary_by_services(partition_date);

    RAISE NOTICE '----------------Calling summary_by_operators----------------';
    CALL public.summary_by_operators(partition_date);
END;
$$;

ALTER PROCEDURE historic_matching_summary_generation(DATE) OWNER TO abods_proxy_rw;


CREATE OR REPLACE PROCEDURE public.populate_headway(IN pt_date DATE)
    LANGUAGE plpgsql
AS
$procedure$
DECLARE
	partition_date DATE := pt_date;
BEGIN
    RAISE NOTICE 'Creating temp_timetable_headway';

    EXECUTE format (
        'drop table if exists public.temp_timetable_headway;'
    );

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
        and (actual_departure_time is not null or timestamp_after_estimate is not null)
        )  x where x.previous_actual_departure_time is not null;',
        partition_date
    );

    RAISE NOTICE 'Updating timetable table with headway data';

    EXECUTE format(
        'update public."Timetable" y

        set headway_time_difference = y.expected_headway - x.actual_headway ,
        actual_headway = x.actual_headway
        from public.temp_timetable_headway x
        where x.timetable_id  = y.timetable_id
        and y.date_of_journey = %L;',
        partition_date
    );

    RAISE NOTICE 'Creating temp_timetable_max_siri_vm_positions_id';

    EXECUTE format (
        'drop table if exists  public.temp_timetable_max_siri_vm_positions_id;'
    );



    EXECUTE format (
        'create table public.temp_timetable_max_siri_vm_positions_id
         as
         select t.timetable_id ,max(sv.siri_vm_positions_id) as max_siri_vm_positions_id  from  public."Timetable" t
         join public."SiriVMPositions" sv
         on t.operator_noc = sv.operator_ref
         and t.line_name = sv.line_name
         and t.journey_code = sv.journey_ref
         and t.date_of_journey = sv.date_of_journey
         and t.actual_departure_time = sv.recorded_at_time

         where t.date_of_journey = %L
         and sv.date_of_journey  = %L
         group by t.timetable_id;',
        partition_date,
        partition_date
    );

    RAISE NOTICE 'Updating timetable table with siri_vm_position_id data';

    EXECUTE format (
        'update public."Timetable" y
        set siri_vm_position_id = x.max_siri_vm_positions_id
        from public.temp_timetable_max_siri_vm_positions_id x
        where x.timetable_id = y.timetable_id
        and y.date_of_journey = %L;'
        , partition_date
    );


    RAISE NOTICE 'Dropping temp tables';

    EXECUTE format (
        'drop table if exists public.temp_timetable_headway;'
    );

    EXECUTE format (
        'drop table if exists  public.temp_timetable_max_siri_vm_positions_id;'
    );
END;
$procedure$;

ALTER PROCEDURE populate_headway(DATE) OWNER TO lingesh;

GRANT EXECUTE ON PROCEDURE populate_headway(DATE) TO jonathan_rw;


CREATE OR REPLACE PROCEDURE public.summary_by_stops(IN partition_date DATE DEFAULT (CURRENT_DATE - '1 day'::INTERVAL))
    LANGUAGE plpgsql
AS
$procedure$
DECLARE
	tablename TEXT;

BEGIN
	tablename := 'timetable_summary_stops_tz_' || to_char(partition_date, 'YYYY_MM_DD');

	RAISE NOTICE 'Creating timetable_summary_stops_tz partition if not exists %', tablename;

	IF EXISTS (
		SELECT 1
		FROM public."Timetable"
		WHERE date_of_journey = partition_date
	) THEN
		RAISE NOTICE '(Re)Creating timetable_summary_stops_tz partition';

		EXECUTE format(
			'CREATE TABLE IF NOT EXISTS public.%I PARTITION OF public.timetable_summary_stops_tz FOR VALUES FROM (%L) TO (%L)',
			tablename,
			partition_date,
			partition_date + INTERVAL '1' DAY
		);

		EXECUTE format('ALTER TABLE public.%I OWNER TO abods_rw', tablename);

		------------------------------
		-- Deleting from partition --
		------------------------------

		RAISE NOTICE 'Deleting from timetable_summary_stops_tz partition';

		EXECUTE format(
			'DELETE FROM public.%I',
			tablename
		);

		----- example insert my new data

		RAISE NOTICE 'Adding new data TO timetable_summary_stops_tz partition';

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

	partition_date := partition_date + INTERVAL '1' DAY;
-- END LOOP;
END;
$procedure$;

ALTER PROCEDURE summary_by_stops(DATE) OWNER TO abods_rw;

GRANT EXECUTE ON PROCEDURE summary_by_stops(DATE) TO jonathan_rw;


CREATE OR REPLACE PROCEDURE public.summary_by_services(IN partition_date DATE DEFAULT (CURRENT_DATE - '1 day'::INTERVAL))
    LANGUAGE plpgsql
AS
$procedure$
DECLARE
	tablename TEXT;

BEGIN
	tablename := 'timetable_summary_service_tz_' || to_char(partition_date, 'YYYY_MM_DD');

	RAISE NOTICE 'Creating timetable_summary_service_tz partition if not exists %', tablename;

	IF EXISTS (
		SELECT 1
		FROM public."Timetable"
		WHERE date_of_journey = partition_date
	) THEN
		RAISE NOTICE '(Re)Creating timetable_summary_service_tz partition';

		EXECUTE format(
			'CREATE TABLE IF NOT EXISTS public.%I PARTITION OF public.timetable_summary_service_tz FOR VALUES FROM (%L) TO (%L)',
			tablename,
			partition_date,
			partition_date + INTERVAL '1' DAY
		);

		EXECUTE format('ALTER TABLE public.%I OWNER TO abods_rw', tablename);

		------------------------------
		-- Deleting from partition --
		------------------------------

		RAISE NOTICE 'Deleting from timetable_summary_service_tz partition';

		EXECUTE format(
			'DELETE FROM public.%I',
			tablename
		);

		----- example insert my new data

		RAISE NOTICE 'Adding new data to timetable_summary_service_tz partition';

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

	partition_date := partition_date + INTERVAL '1' DAY;
-- END LOOP;
END;
$procedure$;

ALTER PROCEDURE summary_by_services(DATE) OWNER TO abods_rw;

GRANT EXECUTE ON PROCEDURE summary_by_services(DATE) TO jonathan_rw;


CREATE OR REPLACE PROCEDURE public.summary_by_operators(IN partition_date DATE DEFAULT (CURRENT_DATE - '1 day'::INTERVAL))
    LANGUAGE plpgsql
AS
$procedure$

DECLARE
	tablename TEXT:= 'timetable_summary_operator_t_' || to_char(partition_date, 'YYYY_MM_DD');

BEGIN
	RAISE NOTICE 'Creating timetable_summary_operator_t partition if not exists %', tablename;
	RAISE NOTICE '(Re)Creating timetable_summary_operator_t partition';

	EXECUTE format(
		'CREATE TABLE if not exists public.%I partition of public.timetable_summary_operator_t FOR VALUES FROM (%L) TO (%L)',
		tablename,
		partition_date,
		partition_date + INTERVAL '1' DAY
	);

	EXECUTE format('
		ALTER TABLE public.%I OWNER TO abods_rw',
		tablename
	);

	------------------------------
	-- Deleting from partition --
	------------------------------

	RAISE NOTICE 'Deleting from timetable_summary_operator_t partition';

	EXECUTE format(
		'DELETE FROM public.%I',
		tablename
	);

	----- example insert my new data

    RAISE NOTICE 'Adding new data to timetable_summary_operator_t partition';

	EXECUTE format(
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
END;
$procedure$;

ALTER PROCEDURE summary_by_operators(DATE) OWNER TO abods_rw;

GRANT EXECUTE ON PROCEDURE summary_by_operators(DATE) TO jonathan_rw;

