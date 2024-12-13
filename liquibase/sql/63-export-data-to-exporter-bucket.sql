CREATE OR REPLACE PROCEDURE public.export_timetable_exporter(IN partition_date date)
 LANGUAGE plpgsql
AS $procedure$

declare 
datestring text:= to_char(partition_date, 'YYYY-MM-DD');
yearstr text:= DATE_PART('year',partition_date);
monthstr text:= DATE_PART('month',partition_date);

begin
	
RAISE NOTICE 'Exporting timetable for date %', partition_date::text;
execute format(
	'SELECT * from aws_s3.query_export_to_s3(
		''select 
			group_id,
			row_number() over( partition by group_id order by group_id,expected_departure_time asc, stop_index  asc  ) as stop_index,
			stop_latitude,
			stop_longitude,
			expected_departure_time::time as expected_departure_time,
			timetable_id,
			date_of_journey,
			direction,
			operator_noc
		from 
			public."Timetable" 
		where
			date_of_journey  = ''''%s''''::date
		order by
			group_id asc,
			expected_departure_time asc,
			stop_index  asc
		'',
	    aws_commons.create_s3_uri(''abods-{SPLIT_PART(aurora_db_instance_identifier(), ''-'', 2)}-exporter-bucket'', ''historic/csv/timetable/YYYY=%s/MM=%s/%s.csv'',  ''eu-west-2''),
		options :=''format csv''
	)',
datestring,
yearstr,
monthstr,
datestring
);
RAISE NOTICE 'Exported timetable for date %', partition_date::text;
end; $procedure$
;


CREATE OR REPLACE PROCEDURE public.export_avl(IN partition_date date)
 LANGUAGE plpgsql
AS $procedure$

declare 
datestring text:= to_char(partition_date, 'YYYY-MM-DD');
yearstr text:= DATE_PART('year',partition_date);
monthstr text:= DATE_PART('month',partition_date);

begin
	

execute format(
	'SELECT * from aws_s3.query_export_to_s3(
	''select * from public."SiriVMPositions" where date_of_journey  = ''''%s''''::date'',
    aws_commons.create_s3_uri(''abods-{SPLIT_PART(aurora_db_instance_identifier(), ''-'', 2)}-exporter-bucket'', ''historic/csv/siri/YYYY=%s/MM=%s/siri_vm_%s.csv'',  ''eu-west-2''),
options :=''format csv''
)',
datestring,
yearstr,
monthstr,
datestring
);
end; $procedure$
;

