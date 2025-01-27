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

CREATE OR REPLACE PROCEDURE public.update_all_transmodel_tables()
 LANGUAGE plpgsql
AS $procedure$
begin
raise notice 'Running update_transmodel_servicepattern at %', current_timestamp;
call public.update_transmodel_servicepattern();
raise notice 'Running update_transmodel_servicepatternstop at %', current_timestamp;
call public.update_transmodel_servicepatternstop();
raise notice 'Running update_organisation_datasetrevision at %', current_timestamp;
call public.update_organisation_datasetrevision();
raise notice 'Running update_organisation_txcfileattributes at %', current_timestamp;
call public.update_organisation_txcfileattributes();
raise notice 'Running update_transmodel_nonoperatingdatesexceptions at %', current_timestamp;
call public.update_transmodel_nonoperatingdatesexceptions();
raise notice 'Running update_transmodel_operatingdatesexceptions at %', current_timestamp;
call public.update_transmodel_operatingdatesexceptions();
raise notice 'Running update_transmodel_operatingprofile at %', current_timestamp;
call public.update_transmodel_operatingprofile();
raise notice 'Running update_transmodel_service at %', current_timestamp;
call public.update_transmodel_service();
raise notice 'Running update_transmodel_service_service_patterns at %', current_timestamp;
call public.update_transmodel_service_service_patterns();
raise notice 'Running update_transmodel_servicedorganisationvehiclejourney at %', current_timestamp;
call public.update_transmodel_servicedorganisationvehiclejourney();
raise notice 'Running update_transmodel_servicedorganisationworkingdays at %', current_timestamp;
call public.update_transmodel_servicedorganisationworkingdays();
raise notice 'Running update_transmodel_vehiclejourney at %', current_timestamp;
call public.update_transmodel_vehiclejourney();
raise notice 'Running update_organisation_dataset at %', current_timestamp;
call public.update_organisation_dataset();
raise notice 'Running update_transmodel_servicepattern_admin_areas at %', current_timestamp;
call public.update_transmodel_servicepattern_admin_areas();
raise notice 'Running update_transmodel_tracks at %', current_timestamp;
call public.update_transmodel_tracks();
end; $procedure$
;

ALTER TABLE public.corridor_stops
ALTER COLUMN corridor_index TYPE INT;