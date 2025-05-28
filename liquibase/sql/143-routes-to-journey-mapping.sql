CREATE TABLE public.route_to_journeys (
    id BIGSERIAL,
    group_id text NOT NULL,
    date_of_journey date NOT NULL,
    distinct_route_id integer NOT NULL
    PRIMARY KEY (id, date_of_journey)
) PARTITION BY RANGE (date_of_journey);

ALTER TABLE public.route_to_journeys OWNER TO abods_rw;

CREATE INDEX idx_route_to_journeys_date_of_journey
ON public.route_to_journeys (
  date_of_journey
);

CREATE INDEX idx_route_to_journeys_distinct_route_id
ON public.route_to_journeys (
  distinct_route_id
);

CREATE INDEX idx_route_to_journeys_group_id
ON public.route_to_journeys (
  group_id
);