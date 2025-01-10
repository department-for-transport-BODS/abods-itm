create or replace procedure create_timetable_threshold_summary(IN pt_date date)
    language plpgsql
as
$$

DECLARE
    partition_date date := pt_date;
    tablename      text;

BEGIN
    tablename := 'timetable_threshold_summary_' || to_char(partition_date, 'YYYY_MM_DD');

    RAISE NOTICE 'Creating partition if not exists %', tablename;

    IF EXISTS (SELECT 1
               FROM public."Timetable"
               WHERE date_of_journey = partition_date
               LIMIT 1) THEN
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
$$;

alter procedure create_timetable_threshold_summary owner to abods_proxy_rw;
