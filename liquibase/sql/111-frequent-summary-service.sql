CREATE TABLE IF NOT EXISTS public.timetable_frequent_summary_services
(
    timetable_id bigserial,
    operator_noc text NOT NULL,
    service_code text NOT NULL,
    noc_and_line_and_servicecode text NOT NULL,
    line_name text NOT NULL,
    date_of_journey date NOT NULL,
    departure_hour timestamp with time zone NOT NULL,
    departure_hour_only time with time zone NOT NULL,
    day_of_week integer NOT NULL,
    max_early integer NOT NULL,
    max_late integer NOT NULL,
    avg_time_difference numeric,
    expected_headway numeric,
    actual_headway numeric,
    excess_wait_time numeric,
    estimated boolean DEFAULT false,
    CONSTRAINT timetable_frequent_summary_services_pkey PRIMARY KEY (service_code, operator_noc, date_of_journey, day_of_week, departure_hour, departure_hour_only, max_early, max_late, noc_and_line_and_servicecode)
) PARTITION BY RANGE (date_of_journey);

ALTER TABLE IF EXISTS public.timetable_frequent_summary_services
    OWNER to abods_proxy_rw;

CREATE INDEX IF NOT EXISTS date_of_journey_stopstz
    ON public.timetable_frequent_summary_services USING btree
    (date_of_journey ASC NULLS LAST)
;


CREATE INDEX IF NOT EXISTS day_of_week_stopstz
    ON public.timetable_frequent_summary_services USING btree
    (day_of_week ASC NULLS LAST)
;


CREATE INDEX IF NOT EXISTS departure_hour_only_stopstz
    ON public.timetable_frequent_summary_services USING btree
    (departure_hour_only ASC NULLS LAST)
;


CREATE INDEX IF NOT EXISTS departure_hour_stopstz
    ON public.timetable_frequent_summary_services USING btree
    (departure_hour ASC NULLS LAST)
;

CREATE INDEX IF NOT EXISTS max_early_stopstz
    ON public.timetable_frequent_summary_services USING btree
    (max_early ASC NULLS LAST)
;


CREATE INDEX IF NOT EXISTS max_late_stopstz
    ON public.timetable_frequent_summary_services USING btree
    (max_late ASC NULLS LAST)
;


CREATE INDEX IF NOT EXISTS noc_and_line_and_servicecode_stopstz
    ON public.timetable_frequent_summary_services USING btree
    (noc_and_line_and_servicecode ASC NULLS LAST)
;


CREATE INDEX IF NOT EXISTS operator_noc_stopstz
    ON public.timetable_frequent_summary_services USING btree
    (operator_noc ASC NULLS LAST)
;


CREATE INDEX IF NOT EXISTS service_code_stopstz
    ON public.timetable_frequent_summary_services USING btree
    (service_code ASC NULLS LAST)
;

CREATE OR REPLACE PROCEDURE public.frequent_summary_services(IN partition_date DATE DEFAULT (CURRENT_DATE - '1 day'::INTERVAL))
    LANGUAGE plpgsql
AS
$procedure$
DECLARE
	tablename TEXT;

BEGIN
	tablename := 'timetable_frequent_summary_services_' || to_char(partition_date, 'YYYY_MM_DD');

	RAISE NOTICE 'Creating timetable_frequent_summary_services partition if not exists %', tablename;

	IF EXISTS (
		SELECT 1
		FROM public."Timetable"
		WHERE date_of_journey = partition_date
	) THEN
		RAISE NOTICE '(Re)Creating timetable_frequent_summary_services partition';

		EXECUTE format(
			'CREATE TABLE IF NOT EXISTS public.%I PARTITION OF public.timetable_frequent_summary_services FOR VALUES FROM (%L) TO (%L)',
			tablename,
			partition_date,
			partition_date + INTERVAL '1' DAY
		);

		EXECUTE format('ALTER TABLE public.%I OWNER TO abods_rw', tablename);

		------------------------------
		-- Deleting from partition --
		------------------------------

		RAISE NOTICE 'Deleting from timetable_frequent_summary_services partition';

		EXECUTE format(
			'DELETE FROM public.%I',
			tablename
		);

		----- example insert my new data

		RAISE NOTICE 'Adding new data TO timetable_frequent_summary_services partition';

		EXECUTE format(
			'INSERT INTO public.%I(
				operator_noc,
				service_code,
				noc_and_line_and_servicecode,
				line_name,
				date_of_journey,
				departure_hour,
				departure_hour_only,
				day_of_week,
				max_early,
				max_late,
				avg_time_difference,
				expected_headway,
				actual_headway,
				excess_wait_Time,
				estimated
			)
			With Timetable_CTE as (SELECT
				sub.operator_noc,
				sub.service_code,
				sub.noc_and_line_and_servicecode,
				sub.line_name,
				sub.date_of_journey,
				date_trunc(''hour'', sub.expected_departure_time::timestamptz) AS departure_hour,
				(EXTRACT(HOUR FROM sub.expected_departure_time)::text || '':00:00'' ||
					CASE
						WHEN RIGHT(sub.expected_departure_time::text, 6)~ ''^[+-]'' THEN RIGHT(sub.expected_departure_time::text, 6)
						ELSE ''+00''
					END
				)::timetz AS departure_hour_only,
				sub.day_of_week,
				sub.max_early,
				sub.max_late,
				COALESCE(AVG(sub.avg_time_difference/60.0), 0.0) AS avg_time_difference,
				AVG(sub.expected_headway) AS expected_headway,
				AVG(sub.actual_headway) FILTER (WHERE sub.actual_headway IS NOT NULL) AS actual_headway,
				AVG(sub.headway_time_difference) FILTER (WHERE sub.actual_headway IS NOT NULL) AS excess_wait_Time,
				sub.estimated,
                sub.stop_id,
                count(sub.stop_id) as stop_count
			FROM
				(
					SELECT
					ttb.operator_noc,
					ttb.service_code,
					es.noc_and_line_and_servicecode,
					ttb.line_name,
					ttb.date_of_journey,
					ttb.day_of_week,
					ttb.expected_departure_time,
					COALESCE(ttb.actual_departure_time, ttb.timestamp_after_estimate) as actual_departure_time,
					ttb.time_difference,
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
					(ttb.timestamp_after_estimate is not null) AS estimated,
                    ttb.stop_id
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
                        and ttb.previous_group_id is not null
				) AS sub
				WHERE
					date_of_journey = %L
				GROUP BY
					operator_noc,
					service_code,
					noc_and_line_and_servicecode,
					stop_id,
					line_name,
					date_of_journey,
					departure_hour,
					departure_hour_only,
					day_of_week,
					max_early,
					max_late,
					estimated
                ),
                Timetable_Agg as (SELECT
                    operator_noc,
                    service_code, 
                    noc_and_line_and_servicecode,
                    line_name,
                    date_of_journey,
                    departure_hour,
                    departure_hour_only,
                    day_of_week,
                    max_early,
                    max_late,
                    avg(avg_time_difference) as avg_time_difference,
                    sum(expected_headway * stop_count) as expected_headway,
                    sum(actual_headway * stop_count) as actual_headway,
                    sum(excess_wait_Time * stop_count) as excess_wait_Time,
                    sum(stop_count) as stop_count,
                    estimated
                FROM 
                    Timetable_CTE
                GROUP BY
                    operator_noc,
					service_code,
					noc_and_line_and_servicecode,
					line_name,
					date_of_journey,
					departure_hour,
					departure_hour_only,
					day_of_week,
					max_early,
					max_late,
					estimated 
                )
                SELECT
                    operator_noc,
                    service_code, 
                    noc_and_line_and_servicecode,
                    line_name,
                    date_of_journey,
                    departure_hour,
                    departure_hour_only
                    day_of_week,
                    max_early,
                    max_late,
                    avg_time_difference,
                    (expected_headway / (stop_count * 60)) as expected_headway,
                    (actual_headway / (stop_count * 60)) as actual_headway,
                    (excess_wait_Time / (stop_count * 60)) as excess_wait_Time,
                    estimated
                FROM
                    Timetable_Agg',
            tablename,
            partition_date,
            partition_date);

		-- EXECUTE format(query, tablename, partition_date, partition_date);
	END IF;

	partition_date := partition_date + INTERVAL '1' DAY;
-- END LOOP;
END;
$procedure$;

ALTER PROCEDURE frequent_summary_services(DATE) OWNER TO abods_rw;

CREATE OR REPLACE PROCEDURE public.historic_matching_summary_generation(IN partition_date DATE)
    LANGUAGE plpgsql
AS
$procedure$
BEGIN
    RAISE NOTICE '----------------Calling generate_expected_tables----------------';
    CALL public.generate_expected_tables(partition_date);

    RAISE NOTICE '----------------Calling create_timetable_threshold_summary----------------';
    CALL public.create_timetable_threshold_summary(partition_date);

    RAISE NOTICE '----------------Calling populate_headway----------------';
    CALL public.populate_headway(partition_date);

    RAISE NOTICE '----------------Calling summary_by_stops----------------';
    CALL public.summary_by_stops(partition_date);

    RAISE NOTICE '----------------Calling frequent_summary_services----------------';
    CALL public.frequent_summary_services(partition_date);

    RAISE NOTICE '----------------Calling summary_by_services----------------';
    CALL public.summary_by_services(partition_date);

    RAISE NOTICE '----------------Calling summary_by_operators----------------';
    CALL public.summary_by_operators(partition_date);
END;
$procedure$;

ALTER PROCEDURE historic_matching_summary_generation(DATE) OWNER TO abods_proxy_rw;
