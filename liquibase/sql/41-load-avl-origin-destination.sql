ALTER TABLE public."staging_avl_positions"
	ADD COLUMN IF NOT EXISTS origin_ref text,
	ADD COLUMN IF NOT EXISTS destination_ref text,
	ADD COLUMN IF NOT EXISTS departure_time timestamp with time zone;

CREATE OR REPLACE FUNCTION public.load_avl_tables(input_batch_id integer)
 RETURNS boolean
 LANGUAGE plpgsql
AS $function$
begin

INSERT INTO public."SiriVMPositions"
    (operator_ref,line_name,journey_ref,date_of_journey, direction_ref,recorded_at_time, response_time_stamp, Latitude, Longitude, vehicle_ref, batch_id, group_id, origin_ref, destination_ref, departure_time)
SELECT 
    operator_ref,
    coalesce(line_name,''),
    journey_ref,
    date_of_journey, 
    direction_ref,
    recorded_at_time::timestamp(0) at TIME zone 'utc', 
    response_timestamp::timestamp(0) at TIME zone 'utc', 
    latitude::real,
    longitude::real,
    vehicle_ref,
    batch_id,
    concat_ws('|', operator_ref, coalesce(line_name,''), journey_ref, to_char(date_of_journey,'YYYY-MM-DD')) as group_id,
    origin_ref,
    destination_ref,
    departure_time::timestamp(0) at TIME zone 'utc'
FROM public.staging_avl_positions pos 
WHERE batch_id=input_batch_id and date_of_journey = now()::date 
ON CONFLICT DO NOTHING
;

DELETE FROM public.staging_avl_positions WHERE batch_id = input_batch_id;

RETURN true;

END;$function$
;