ALTER TABLE public."SiriVMPositions"
	ADD COLUMN IF NOT EXISTS origin_ref text,
	ADD COLUMN IF NOT EXISTS destination_ref text,
	ADD COLUMN IF NOT EXISTS departure_time timestamp with time zone;