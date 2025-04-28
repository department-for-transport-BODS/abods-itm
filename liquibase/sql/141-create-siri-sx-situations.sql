CREATE TABLE public.siri_sx_situations (
    id SERIAL PRIMARY KEY,
    producer_ref TEXT NOT NULL,
    situation_number TEXT NOT NULL,
    version TEXT,
    operator_noc TEXT,
    line_name TEXT,
    direction TEXT,
    date_of_journey TIMESTAMPTZ,
    start_date TIMESTAMPTZ,
    end_date TIMESTAMPTZ,
    journey_code TEXT,
    condition TEXT,
    progress TEXT,
    event_timestamp TIMESTAMPTZ,
    creation_time TIMESTAMPTZ,
    UNIQUE (producer_ref, situation_number, version)
);

CREATE INDEX idx_situations_date_of_journey
ON public.siri_sx_situations (
  date_of_journey
)

ALTER TABLE public.siri_sx_situations OWNER TO abods_rw;