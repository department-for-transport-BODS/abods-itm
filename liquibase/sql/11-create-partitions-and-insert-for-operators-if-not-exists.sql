
-- CREATE PARTITIONS DYNAMICALLY FOR timetable_summary_operators AND POPULATE TABLE WITH PREVIOUS DAY DATA -----

-- PROCEDURE: public.create_partition_operators_if_not_exists()

DROP PROCEDURE IF EXISTS public.create_partition_operators_if_not_exists();


CREATE OR REPLACE PROCEDURE public.create_partition_operators_if_not_exists(
	)
LANGUAGE 'plpgsql'
AS $BODY$

declare   
	partition_date date:= current_date - interval '1 day';
	tablename text:= 'timetable_summary_operator_' || to_char(partition_date, 'YYYY_MM_DD');

begin
	RAISE NOTICE 'Creating partition if not exists %', tablename;
	RAISE NOTICE '(Re)Creating partition';
	
	execute format(
		'CREATE TABLE if not exists public.%I partition of public.timetable_summary_operator FOR VALUES FROM (%L) TO (%L)',
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
	
	-----  insert my new data

	execute format(
	  'INSERT INTO public.%I (
      operator_noc,
	    date_of_journey,
	    departure_hour,
	    day_of_week,
	  	on_time_count, 
	  	early_count, 
	  	late_count, 
	  	completed, 
  		scheduled, 
	    is_timing_point,
  		max_early,
  		max_late,
  		avg_time_difference
	)
	SELECT 
		sub.operator_noc,
	    sub.date_of_journey,
		date_trunc(''hour'', sub.expected_departure_time) AS departure_hour,
	    sub.day_of_week,
		COUNT(CASE WHEN sub.otp_state = ''OnTime'' THEN 1 END) AS on_time_count,  
		COUNT(CASE WHEN sub.otp_state = ''Early'' THEN 1 END) AS early_count, 
		COUNT(CASE WHEN sub.otp_state = ''Late'' THEN 1 END) AS late_count, 
		COUNT(sub.actual_departure_time) AS completed,
		COUNT(*) AS scheduled,
	    sub.is_timing_point,
		sub.max_early,
		sub.max_late,
		COALESCE(AVG(sub.avg_time_difference/60.0), 0.0) AS avg_time_difference
	FROM 
		(
			SELECT 
			  operator_noc,
		    operator_name,
		    service_code,
		    line_name,
		    date_of_journey,
		    day_of_week,
		    common_name,
		    expected_departure_time ,
		    actual_departure_time,
		    is_timing_point,
		    otp_state,
		    time_difference,
		    stop_id,
		  	stop_latitude,
		    stop_longitude,
			  locality_id,
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
			time_difference AS avg_time_difference
		FROM 
			public."Timetable"
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
		is_timing_point, 
		max_early, 
		max_late',
	  tablename,
	  partition_date,
	  partition_date
);
end; 
$BODY$;

-- CHANGE OWNERSHIP -----------

ALTER PROCEDURE public.create_partition_operators_if_not_exists()
    OWNER TO abods_rw;

-- SCHEDULE THE PROCEDURE -------------

SELECT cron.schedule('create_partition_operators_if_not_exists', 
	'0 2 * * *', $$CALL public.create_partition_operators_if_not_exists()$$);

-- END ---
