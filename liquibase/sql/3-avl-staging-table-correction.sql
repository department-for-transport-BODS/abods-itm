DROP TABLE IF EXISTS public.staging_timetable_avl_positions;

CREATE TABLE IF NOT EXISTS public.staging_avl_positions (
	recorded_at_time text NULL,
	response_timestamp text NULL,
	latitude text NULL,
	longitude text NULL,
	line_name text NULL,
	operator_ref text NULL,
	vehicle_ref text NULL,
	journey_ref text NULL,
	direction_ref text NULL,
	date_of_journey date NULL,
	batch_id int4 NULL,
	load_timestamp timestamp(0) DEFAULT now()::timestamp(0) without time zone NULL
);
CREATE INDEX IF NOT EXISTS idx_batch_id ON public.staging_avl_positions USING btree (batch_id);
