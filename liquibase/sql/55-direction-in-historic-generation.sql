CREATE OR REPLACE PROCEDURE export_timetable(IN partition_date date)
    LANGUAGE plpgsql
AS
$$

declare 
datestring text:= to_char(partition_date, 'YYYY-MM-DD');
env text:= 'sandbox'; -- TODO: GET THIS SOMEHOW

begin
	
RAISE NOTICE 'Exporting timetable for date %', partition_date::text;
execute format(
	'SELECT * from aws_s3.query_export_to_s3(
		''select 
			group_id,
			row_number() over( partition by vehiclejourney_id order by group_id,expected_departure_time asc, stop_index  asc  ) as stop_index,
			stop_latitude,
			stop_longitude,
			expected_departure_time::time as expected_departure_time,
			timetable_id,
			date_of_journey,
			direction
		from 
			public."Timetable" 
		where
			date_of_journey  = ''''%s''''::date
		order by
			group_id asc,
			expected_departure_time asc,
			stop_index  asc
		'',
	    aws_commons.create_s3_uri(''abods-%s-process-bucket'', ''historic_timetable/%s.csv'',  ''eu-west-2''),
		options :=''format csv''
	)',
datestring,
env,
datestring
);
RAISE NOTICE 'Exported timetable for date %', partition_date::text;
end; $$;

alter procedure export_timetable(date) owner to root;

grant execute on procedure export_timetable(date) to jonathan_rw;

