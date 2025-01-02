-- AVL import is split into 3 functions to avoid holding a lock on the SiriVMPositions table while the data is imported

create or replace procedure prep_historic_avl_table(IN partition_date date)
    language plpgsql
as
$$

declare
    longdatestring   text := to_char(partition_date, 'YYYY_MM_DD');
    timetable_suffix text := concat('_', longdatestring);
    tablename        text := 'SiriVMPositions';

begin

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

    execute format('
	ALTER TABLE public.%I detach partition public.%I',
                   tablename,
                   concat(tablename, '_p', longdatestring)
            );

end;
$$;

alter procedure prep_historic_avl_table owner to abods_proxy_rw;

create or replace procedure import_historic_avl(IN partition_date date)
    language plpgsql
as
$$

declare
    longdatestring   text := to_char(partition_date, 'YYYY_MM_DD');
    timetable_suffix text := concat('_', longdatestring);
    tablename        text := 'SiriVMPositions';

begin

    execute format(
            'TRUNCATE TABLE %L',
            concat(tablename, '_p', longdatestring)
            );

    execute format(
            'SELECT aws_s3.table_import_from_s3(
    ''"%s"'',
    ''group_id,recorded_at_time,response_time_stamp,latitude,longitude,line_name,operator_ref,vehicle_ref,journey_ref,direction_ref,date_of_journey,origin_ref,destination_ref,departure_time'',
    ''(FORMAT csv, HEADER True, DELIMITER ",")'',
    ''abods-prod-exporter-bucket'',
    ''historic/gz/YYYY=%s/MM=%s/DD=%s/%s.csv.gz'',
    ''eu-west-2'')
',
            concat(tablename, '_p', longdatestring),
            to_char(partition_date, 'YYYY'),
            to_char(partition_date, 'MM'),
            to_char(partition_date, 'DD'),
            to_char(partition_date, 'YYYY-MM-DD')
            );

end;
$$;

alter procedure import_historic_avl owner to abods_proxy_rw;

create or replace procedure attach_historic_avl_table(IN partition_date date)
    language plpgsql
as
$$

declare
    longdatestring   text := to_char(partition_date, 'YYYY_MM_DD');
    timetable_suffix text := concat('_', longdatestring);
    tablename        text := 'SiriVMPositions';

begin


    execute format(
            'ALTER TABLE public.%I attach partition public.%I
FOR VALUES FROM (%L) TO (%L)',
            tablename,
            concat(tablename, '_p', longdatestring),
            partition_date,
            partition_date + interval '1' day);

end;
$$;

alter procedure attach_historic_avl_table owner to abods_proxy_rw;
