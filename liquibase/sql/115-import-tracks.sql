IMPORT FOREIGN SCHEMA public LIMIT TO (
    transmodel_tracks
)
FROM SERVER bods INTO bods;

GRANT SELECT ON TABLE bods."transmodel_tracks" TO abods_rw;

CREATE TABLE public.transmodel_tracks (
	id bigint,
	from_atco_code varchar(255) NOT NULL,
	to_atco_code varchar(255) NOT NULL,
    geometry text NULL,
	distance int4 NULL,
	CONSTRAINT transmodel_tracks_pkey PRIMARY KEY (id),
	CONSTRAINT unique_from_to_atco_code UNIQUE (from_atco_code, to_atco_code)
);
alter table public.transmodel_tracks owner to abods_rw;
CREATE INDEX transmodel_tracks_geometry_idx ON public.transmodel_tracks USING btree (from_atco_code, to_atco_code);

SELECT cron.schedule('sync_tracks', '05 15 * * *', $$CALL public.sync_tracks();$$);