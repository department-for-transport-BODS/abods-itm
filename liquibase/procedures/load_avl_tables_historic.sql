create or replace procedure load_avl_tables_historic(IN pt_date date)
    language plpgsql
as
$$
DECLARE
    partition_date date := pt_date;
    tablename      text;

BEGIN
    tablename := 'SiriVMPositions_p' || to_char(partition_date, 'YYYY_MM_DD');

    EXECUTE format(
            'CREATE TABLE IF NOT EXISTS public.%I PARTITION OF public."SiriVMPositions" FOR VALUES FROM (%L) TO (%L)',
            tablename,
            partition_date,
            partition_date + interval '1' day
            );

    EXECUTE format('ALTER TABLE public.%I OWNER TO abods_rw', tablename);

    EXECUTE format('INSERT INTO public.%I
(operator_ref,line_name,journey_ref,date_of_journey, direction_ref,recorded_at_time, response_time_stamp, Latitude, Longitude, vehicle_ref, batch_id, group_id)

select
operator_ref,
coalesce(line_name,''''),
journey_ref,
date_of_journey,
direction_ref,
recorded_at_time::timestamp(0) at TIME zone ''utc'',
response_timestamp::timestamp(0) at TIME zone ''utc'',
latitude::real,
longitude::real,
vehicle_ref,
batch_id,
LOWER(concat_ws(''|'',operator_ref,coalesce(line_name,''''),journey_ref,to_char(date_of_journey,''YYYY-MM-DD''))) as group_id

from public.staging_avl_positions_historic pos

where  date_of_journey = %L
ON CONFLICT DO NOTHING
;', tablename, partition_date);

    EXECUTE format('truncate public.staging_avl_positions_historic;');

END;
$$;
