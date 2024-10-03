--changeset abodsuser:1

-- Foreign Table: bods.%
IMPORT FOREIGN SCHEMA public LIMIT TO (
    naptan_adminarea,
    naptan_locality,
    naptan_stoppoint,
    organisation_datasetrevision,
    organisation_operatorcode,
    organisation_organisation,
    organisation_organisation_admin_areas,
    organisation_txcfileattributes,
    transmodel_nonoperatingdatesexceptions,
    transmodel_operatingdatesexceptions,
    transmodel_operatingprofile,
    transmodel_service,
    transmodel_service_service_patterns, 
    transmodel_servicedorganisations,
    transmodel_servicedorganisationvehiclejourney,
    transmodel_servicedorganisationworkingdays,
    transmodel_servicepattern,
    transmodel_servicepattern_admin_areas,
    transmodel_servicepatternstop,
    transmodel_vehiclejourney,
    users_user,
    users_user_organisations
)
FROM SERVER bods INTO bods;

GRANT SELECT ON TABLE bods."naptan_adminarea" TO abods_rw;
GRANT SELECT ON TABLE bods."naptan_locality" TO abods_rw;
GRANT SELECT ON TABLE bods."naptan_stoppoint" TO abods_rw;
GRANT SELECT ON TABLE bods."organisation_datasetrevision" TO abods_rw;
GRANT SELECT ON TABLE bods."organisation_operatorcode" TO abods_rw;
GRANT SELECT ON TABLE bods."organisation_organisation" TO abods_rw;
GRANT SELECT ON TABLE bods."organisation_organisation_admin_areas" TO abods_rw;
GRANT SELECT ON TABLE bods."organisation_txcfileattributes" TO abods_rw;
GRANT SELECT ON TABLE bods."transmodel_nonoperatingdatesexceptions" TO abods_rw;
GRANT SELECT ON TABLE bods."transmodel_operatingdatesexceptions" TO abods_rw;
GRANT SELECT ON TABLE bods."transmodel_operatingprofile" TO abods_rw;
GRANT SELECT ON TABLE bods."transmodel_service" TO abods_rw;
GRANT SELECT ON TABLE bods."transmodel_service_service_patterns" TO abods_rw;
GRANT SELECT ON TABLE bods."transmodel_servicedorganisations" TO abods_rw;
GRANT SELECT ON TABLE bods."transmodel_servicedorganisationvehiclejourney" TO abods_rw;
GRANT SELECT ON TABLE bods."transmodel_servicedorganisationworkingdays" TO abods_rw;
GRANT SELECT ON TABLE bods."transmodel_servicepattern" TO abods_rw;
GRANT SELECT ON TABLE bods."transmodel_servicepattern_admin_areas" TO abods_rw;
GRANT SELECT ON TABLE bods."transmodel_servicepatternstop" TO abods_rw;
GRANT SELECT ON TABLE bods."transmodel_vehiclejourney" TO abods_rw;
GRANT SELECT ON TABLE bods."users_user" TO abods_rw;
GRANT SELECT ON TABLE bods."users_user_organisations" TO abods_rw;

-- Table: public.Alert
CREATE TABLE IF NOT EXISTS public."Alert"
(
    id character varying(100) COLLATE pg_catalog."default" NOT NULL,
    alert_id character varying(100) COLLATE pg_catalog."default",
    alert character varying(100) COLLATE pg_catalog."default",
    event_hysterisis numeric(10,0),
    event_threshold numeric(10,0),
    send_to integer,
    created_by integer,
    CONSTRAINT "Alert_pkey" PRIMARY KEY (id)
);

-- Table: public.Tokens
 CREATE TABLE IF NOT EXISTS public."Tokens"
(
    user_id integer NOT NULL,
    token character varying(150) COLLATE pg_catalog."default",
    CONSTRAINT "Tokens_pkey" PRIMARY KEY (user_id)
);

-- Table: public.FeatureFlag
CREATE TABLE IF NOT EXISTS public."FeatureFlag"
(
    id character varying(100) COLLATE pg_catalog."default" NOT NULL,
    consolidate_histogram boolean NOT NULL,
    corridor_stats_timezone_enabled boolean NOT NULL,
    freshdesk_enabled boolean NOT NULL,
    line_direction_filtering boolean NOT NULL,
    sso_enabled boolean NOT NULL,
    stop_index_filtering boolean NOT NULL,
    tagging_include_bank_holidays boolean NOT NULL,
    vehicle_replay_from_timestream boolean NOT NULL,
    journey_insights_enabled boolean NOT NULL,
    CONSTRAINT "FeatureFlag_pkey" PRIMARY KEY (id)
);

-- Table: public.ApiInfo
CREATE TABLE IF NOT EXISTS public."ApiInfo"
(
    id character varying(100) COLLATE pg_catalog."default" NOT NULL,
    version text COLLATE pg_catalog."default" NOT NULL,
    build_number text COLLATE pg_catalog."default" NOT NULL,
    timezone text COLLATE pg_catalog."default" NOT NULL,
    feature_flag_id character varying(100) COLLATE pg_catalog."default" NOT NULL,
    CONSTRAINT "ApiInfo_pkey" PRIMARY KEY (id),
    CONSTRAINT "RefFeatureFlag12" FOREIGN KEY (feature_flag_id)
        REFERENCES public."FeatureFlag" (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE NO ACTION
);

-- Table: public.traveline_operators
CREATE TABLE IF NOT EXISTS traveline_operators (
    noc_code varchar NOT NULL,
    "name" varchar NULL,
    licence varchar NULL,
    "mode" varchar NULL,
    CONSTRAINT travelinedata_pk PRIMARY KEY (noc_code)
);

-- -- Table: public.NaptanAdminArea
-- CREATE TABLE IF NOT EXISTS public."NaptanAdminArea"
-- (
--     naptan_admin_area_id integer NOT NULL,
--     name character varying(255) COLLATE pg_catalog."default" NOT NULL,
--     travelline_region_id character varying(255) COLLATE pg_catalog."default" NOT NULL,
--     atco_code character varying(255) COLLATE pg_catalog."default" NOT NULL,
--     CONSTRAINT "naptanadminArea_pkey01" PRIMARY KEY (naptan_admin_area_id),
--     CONSTRAINT "NaptanAdminArea_atco_code_key01" UNIQUE (atco_code)
-- );

-- -- Table: public.NaptanLocality
-- CREATE TABLE IF NOT EXISTS public."NaptanLocality"
-- (
--     gazetteer_id character varying(8) COLLATE pg_catalog."default" NOT NULL,
--     name character varying(255) COLLATE pg_catalog."default" NOT NULL,
--     easting integer,
--     northing integer,
--     naptan_admin_area_id integer,
--     CONSTRAINT naptanlocality_pkey01 PRIMARY KEY (gazetteer_id),
--     CONSTRAINT refadminarea FOREIGN KEY (naptan_admin_area_id)
--         REFERENCES public."NaptanAdminArea" (naptan_admin_area_id) MATCH SIMPLE
--         ON UPDATE NO ACTION
--         ON DELETE NO ACTION
-- );

-- -- Table: public.ExpectedOperators
-- CREATE TABLE IF NOT EXISTS public."ExpectedOperators"
-- (
--     expected_operator_id integer NOT NULL,
--     noc text COLLATE pg_catalog."default",
--     organisation_id integer,
--     operator_name character varying(100) COLLATE pg_catalog."default",
--     CONSTRAINT expectedoperators_pkey01 PRIMARY KEY (expected_operator_id)
-- );

-- -- Table: public.ExpectedServices
-- CREATE TABLE IF NOT EXISTS public."ExpectedServices"
-- (
--     expected_service_id integer NOT NULL,
--     service_name text COLLATE pg_catalog."default" NOT NULL,
--     expected_operator_id integer,
--     CONSTRAINT expectedservices_pkey01 PRIMARY KEY (expected_service_id),
--     CONSTRAINT expected_operator_fk FOREIGN KEY (expected_operator_id)
--         REFERENCES public."ExpectedOperators" (expected_operator_id) MATCH SIMPLE
--         ON UPDATE NO ACTION
--         ON DELETE NO ACTION
--         NOT VALID
-- );

-- -- Table: public.OperatorAdminArea
-- CREATE TABLE IF NOT EXISTS public."OperatorAdminArea"
-- (
--     operator_admin_area_id integer NOT NULL,
--     naptan_admin_area_id integer,
--     expected_operator_id integer,
--     CONSTRAINT "opeatoradminarea_pkey01" PRIMARY KEY (operator_admin_area_id),
--     CONSTRAINT "RefNaptanAdminArea03" FOREIGN KEY (naptan_admin_area_id)
--         REFERENCES public."NaptanAdminArea" (naptan_admin_area_id) MATCH SIMPLE
--         ON UPDATE NO ACTION
--         ON DELETE NO ACTION
--         NOT VALID
-- );

-- Table: public.SiriVMPositions
CREATE TABLE IF NOT EXISTS public."SiriVMPositions"
(
    siri_vm_positions_id bigserial NOT NULL,
    operator_ref text COLLATE pg_catalog."default" NOT NULL,
    line_name text COLLATE pg_catalog."default" NOT NULL,
    journey_ref text COLLATE pg_catalog."default" NOT NULL,
    direction_ref text COLLATE pg_catalog."default",
    date_of_journey date NOT NULL,
    latitude real,
    longitude real,
    vehicle_ref text COLLATE pg_catalog."default" NOT NULL,
    batch_id bigint,
    recorded_at_time timestamp without time zone NOT NULL,
    response_time_stamp timestamp without time zone,
    load_time_stamp timestamp without time zone DEFAULT now(),
    CONSTRAINT siri_positions_vehicleref_recordedattime_30052024 PRIMARY KEY (operator_ref, line_name, journey_ref, date_of_journey, vehicle_ref, recorded_at_time)
) PARTITION BY RANGE (date_of_journey);


SELECT partman.create_parent(p_parent_table => 'public.SiriVMPositions',
    p_control => 'date_of_journey',
    p_type => 'native',
    p_interval=> 'daily',
    p_premake => 30
);
 
UPDATE partman.part_config
SET infinite_time_partitions = true,
    retention = '1200 months',
    retention_keep_table=false
WHERE parent_table = 'public.SiriVMPositions';
 
SELECT cron.schedule('15 23 * * *', $$CALL partman.run_maintenance_proc()$$);
SELECT cron.schedule('00 22 * * *', $$CALL partman.partition_data_proc('public.SiriVMPositions')$$);

-- View: public.all_operators
CREATE VIEW public.all_operators AS SELECT oo.id AS operatorid,
    to2.noc_code AS operatorref,
        CASE
            WHEN (to2.name IS NULL) THEN (concat('Not in Traveline: ', oo.noc))::character varying
            ELSE to2.name
        END AS name
   FROM (bods.organisation_operatorcode oo
     FULL JOIN traveline_operators to2 ON (((oo.noc)::text = (to2.noc_code)::text)))
  GROUP BY oo.id, to2.noc_code,
        CASE
            WHEN (to2.name IS NULL) THEN (concat('Not in Traveline: ', oo.noc))::character varying
            ELSE to2.name
        END;

-- View: public.bods_operators
CREATE VIEW public.bods_operators AS SELECT id AS operatorid,
    noc AS operatorref
   FROM bods.organisation_operatorcode oo
  GROUP BY id, noc;

-- View: public.bods_organisation
CREATE VIEW public.bods_organisation AS WITH all_orgs AS (
         SELECT oo.id,
            oo.name,
                CASE
                    WHEN ((uu.email)::text ~~ '%kpmg.co.uk'::text) THEN true
                    ELSE false
                END AS is_abods_global_viewer
           FROM (((bods.organisation_organisation oo
             LEFT JOIN bods.users_user_organisations uuo ON ((oo.id = uuo.organisation_id)))
             LEFT JOIN bods.users_user uu ON ((uuo.user_id = uu.id)))
             LEFT JOIN bods.organisation_operatorcode oo2 ON ((oo.id = oo2.organisation_id)))
          WHERE ((oo2.noc IS NOT NULL) OR ((uu.email)::text ~~ '%kpmg.co.uk'::text))
        )
 SELECT id,
    name,
    bool_or(is_abods_global_viewer) AS is_abods_global_viewer
   FROM all_orgs
  GROUP BY id, name;

-- View: public.bods_organisationoperator
CREATE VIEW public.bods_organisationoperator AS SELECT oo.organisation_id,
    oo.noc AS operatorref
   FROM (bods_organisation bo
     LEFT JOIN bods.organisation_operatorcode oo ON ((bo.id = oo.organisation_id)))
  GROUP BY oo.organisation_id, oo.noc
UNION
 SELECT bo.id AS organisation_id,
    ao.operatorref
   FROM (bods_organisation bo
     CROSS JOIN all_operators ao)
  WHERE (bo.is_abods_global_viewer = true)
  GROUP BY bo.id, ao.operatorref;

-- View: public.bods_userorganisation
CREATE VIEW public.bods_userorganisation AS SELECT uuo.user_id,
    uuo.organisation_id
   FROM (bods_organisation bo
     LEFT JOIN bods.users_user_organisations uuo ON ((bo.id = uuo.organisation_id)))
  GROUP BY uuo.user_id, uuo.organisation_id;

-- View: public.bods_user
CREATE VIEW public.bods_user AS SELECT uu.id,
    uu.username,
    uu.email,
    uu.first_name,
    uu.last_name,
    uu.password,
    uu.is_superuser,
    uu.is_active
   FROM (bods_userorganisation bu
     LEFT JOIN bods.users_user uu ON ((bu.user_id = uu.id)))
  GROUP BY uu.id, uu.username, uu.email, uu.first_name, uu.last_name, uu.password, uu.is_superuser, uu.is_active;

-- Function: public.load_avl_tables
CREATE OR REPLACE FUNCTION public.load_avl_tables(input_batch_id integer)
 RETURNS boolean
 LANGUAGE plpgsql
AS $function$
begin


INSERT INTO public."SiriVMPositions"
(operator_ref,line_name,journey_ref,date_of_journey, direction_ref,recorded_at_time, response_time_stamp, Latitude, Longitude, vehicle_ref, batch_id)

select 
operator_ref,
coalesce(line_name,''),
journey_ref,
date_of_journey, 
direction_ref,
recorded_at_time::timestamp(0), 
response_timestamp::timestamp(0), 
latitude::real,
longitude::real,
vehicle_ref,
batch_id

from public.staging_avl_positions pos 

where batch_id=input_batch_id
and date_of_journey = now()::date 
ON CONFLICT DO NOTHING
;

delete from public.staging_avl_positions where batch_id =  input_batch_id;

RETURN true;

END;$function$
;


CREATE TABLE IF NOT EXISTS public.staging_timetable_avl_positions (
operator_ref text NOT NULL,
line_name text NOT NULL,
journey_code date NOT NULL,
date_of_journey text,
stop_id text,
timetable_id bigint,
actual text,
diff_in_secs text,
state text,
siri_vm_position_id bigint
);

-- Table: public.batch
CREATE TABLE IF NOT EXISTS public.batch
(
    batch_id serial NOT NULL,
    batch_dt date,
    process_cd character varying(50) COLLATE pg_catalog."default",
    s3_ingestion_strt_prc_ts timestamp without time zone,
    s3_ingestion_end_prc_ts timestamp without time zone,
    db_ingestion_strt_prc_ts timestamp without time zone,
    db_ingestion_end_prc_ts timestamp without time zone,
    s3_ingestion_status character varying(50) COLLATE pg_catalog."default",
    db_ingestion_status character varying(50) COLLATE pg_catalog."default",
    s3_avl_gip_key character varying(500) COLLATE pg_catalog."default",
    s3_avl_gz_key character varying(500) COLLATE pg_catalog."default",
    otp_update_status text COLLATE pg_catalog."default"
);

-- Table: public.sirivm_matching_batch
CREATE TABLE IF NOT EXISTS public.sirivm_matching_batch
(
    batch_id serial,
    batch_dt date,
    last_processed_timestamp timestamp without time zone
);

-- Table: public.transmodel_servicepattern

CREATE TABLE if not exists public.transmodel_servicepattern (
	id bigint NOT NULL,
	service_pattern_id text NOT NULL,
	origin text NOT NULL,
	destination text NOT NULL,
	description text NULL,
	geom public.geometry(linestring, 4326) NULL,
	revision_id int4 NULL,
	line_name text null,
	CONSTRAINT transmodel_servicepattern_pkey PRIMARY KEY (id)
);
alter table public.transmodel_servicepattern owner to abods_rw;
CREATE INDEX ON public.transmodel_servicepattern (revision_id);


create or replace procedure public.update_transmodel_servicepattern()
 LANGUAGE plpgsql
AS $procedure$
declare 
max_current int:= coalesce((select max(id) from public.transmodel_servicepattern), 0);
begin
insert into public.transmodel_servicepattern (
	id,
	service_pattern_id,
	origin,
	destination,
	description,
	geom,
	revision_id,
	line_name
)
select
	id,
	service_pattern_id,
	origin,
	destination,
	description,
	geom,
	revision_id,
	line_name
 from bods.transmodel_servicepattern ts
where ts.id > max_current
on conflict do nothing;
end; $procedure$
;
alter procedure public.update_transmodel_servicepattern owner to abods_rw;

-- Table: public.transmodel_servicepatternstop

CREATE TABLE if not exists public.transmodel_servicepatternstop (
	id bigint NOT NULL,
	sequence_number int4 NOT NULL,
	atco_code text NOT NULL,
	naptan_stop_id int4 NULL,
	service_pattern_id int4 NOT NULL,
	departure_time time NULL,
	is_timing_point bool NOT NULL,
	txc_common_name text NULL,
	vehicle_journey_id int4 NULL,
	stop_activity_id int4 NULL,
	CONSTRAINT transmodel_servicepatternstop_pkey PRIMARY KEY (id)
);
alter table public.transmodel_servicepatternstop owner to abods_rw;
CREATE INDEX ON public.transmodel_servicepatternstop (naptan_stop_id);
CREATE INDEX ON public.transmodel_servicepatternstop (service_pattern_id);
CREATE INDEX ON public.transmodel_servicepatternstop (vehicle_journey_id);


create or replace procedure public.update_transmodel_servicepatternstop()
 LANGUAGE plpgsql
AS $procedure$
declare 
max_current int:= coalesce((select max(id) from public.transmodel_servicepatternstop), 0);
begin
insert into public.transmodel_servicepatternstop (
	id,
	sequence_number,
	atco_code,
	naptan_stop_id,
	service_pattern_id,
	departure_time,
	is_timing_point,
	txc_common_name,
	vehicle_journey_id,
	stop_activity_id
)
select
	id,
	sequence_number,
	atco_code,
	naptan_stop_id,
	service_pattern_id,
	departure_time,
	is_timing_point,
	txc_common_name,
	vehicle_journey_id,
	stop_activity_id
 from bods.transmodel_servicepatternstop ts
where ts.id > max_current
on conflict do nothing;
end; $procedure$
;
alter procedure public.update_transmodel_servicepatternstop owner to abods_rw;

-- Table: public.organisation_datasetrevision

CREATE TABLE if not exists public.organisation_datasetrevision (
	id bigint primary key,
	created timestamptz NOT NULL,
	modified timestamptz NOT NULL,
	upload_file text NULL,
	status text NOT NULL,
	"name" text NOT NULL,
	description text NOT NULL,
	"comment" text NOT NULL,
	is_published bool NOT NULL,
	url_link text NOT NULL,
	num_of_lines int4 NULL,
	num_of_operators int4 NULL,
	transxchange_version text NOT NULL,
	imported timestamptz NULL,
	bounding_box text NULL,
	publisher_creation_datetime timestamptz NULL,
	publisher_modified_datetime timestamptz NULL,
	first_expiring_service timestamptz NULL,
	last_expiring_service timestamptz NULL,
	first_service_start timestamptz NULL,
	num_of_bus_stops int4 NULL,
	dataset_id int4 NOT NULL,
	last_modified_user_id int4 NULL,
	published_by_id int4 NULL,
	published_at timestamptz NULL,
	"password" text NOT NULL,
	requestor_ref text NOT NULL,
	username text NOT NULL,
	short_description text NOT NULL,
	num_of_timing_points int4 NULL
);
alter table public.organisation_datasetrevision owner to abods_rw;

create or replace procedure public.update_organisation_datasetrevision()
 LANGUAGE plpgsql
AS $procedure$
declare 
max_current int:= coalesce((select max(id) from public.organisation_datasetrevision), 0);
begin
insert into public.organisation_datasetrevision (
	id,
	created,
	modified,
	upload_file,
	status,
	"name",
	description,
	"comment",
	is_published,
	url_link,
	num_of_lines,
	num_of_operators,
	transxchange_version,
	imported,
	bounding_box,
	publisher_creation_datetime,
	publisher_modified_datetime,
	first_expiring_service,
	last_expiring_service,
	first_service_start,
	num_of_bus_stops,
	dataset_id,
	last_modified_user_id,
	published_by_id,
	published_at,
	"password",
	requestor_ref,
	username,
	short_description,
	num_of_timing_points
)
select
	id,
	created,
	modified,
	upload_file,
	status,
	"name",
	description,
	"comment",
	is_published,
	url_link,
	num_of_lines,
	num_of_operators,
	transxchange_version,
	imported,
	bounding_box,
	publisher_creation_datetime,
	publisher_modified_datetime,
	first_expiring_service,
	last_expiring_service,
	first_service_start,
	num_of_bus_stops,
	dataset_id,
	last_modified_user_id,
	published_by_id,
	published_at,
	"password",
	requestor_ref,
	username,
	short_description,
	num_of_timing_points
 from bods.organisation_datasetrevision od
where od.id > max_current
on conflict do nothing;
end; $procedure$
;
alter procedure public.update_organisation_datasetrevision owner to abods_rw;

-- Table: public.organisation_txcfileattributes

CREATE TABLE if not exists public.organisation_txcfileattributes (
	id bigint primary key,
	schema_version text NOT NULL,
	revision_number int4 NOT NULL,
	creation_datetime timestamptz NOT NULL,
	modification_datetime timestamptz NOT NULL,
	filename text NOT NULL,
	service_code text NOT NULL,
	revision_id int4 NOT NULL,
	modification text NOT NULL,
	national_operator_code text NOT NULL,
	licence_number text NOT NULL,
	operating_period_end_date date NULL,
	operating_period_start_date date NULL,
	public_use bool NOT NULL,
	line_names _text NOT NULL,
	destination text NOT NULL,
	origin text NOT NULL,
	hash text NOT NULL
);
alter table public.organisation_txcfileattributes owner to abods_rw;
CREATE INDEX ON public.organisation_txcfileattributes (revision_id);

create or replace procedure public.update_organisation_txcfileattributes()
 LANGUAGE plpgsql
AS $procedure$
declare 
max_current int:= coalesce((select max(id) from public.organisation_txcfileattributes), 0);
begin
insert into public.organisation_txcfileattributes (
	id,
	schema_version,
	revision_number,
	creation_datetime,
	modification_datetime,
	filename,
	service_code,
	revision_id,
	modification,
	national_operator_code,
	licence_number,
	operating_period_end_date,
	operating_period_start_date,
	public_use,
	line_names,
	destination,
	origin,
	hash
)
select
	id,
	schema_version,
	revision_number,
	creation_datetime,
	modification_datetime,
	filename,
	service_code,
	revision_id,
	modification,
	national_operator_code,
	licence_number,
	operating_period_end_date,
	operating_period_start_date,
	public_use,
	line_names,
	destination,
	origin,
	hash
 from bods.organisation_txcfileattributes ot
where ot.id > max_current
on conflict do nothing;
end; $procedure$
;
alter procedure public.update_organisation_txcfileattributes owner to abods_rw;

-- Table: public.transmodel_nonoperatingdatesexceptions

CREATE TABLE if not exists public.transmodel_nonoperatingdatesexceptions (
	id bigint primary key,
	non_operating_date date NULL,
	vehicle_journey_id int4 NOT NULL
);
alter table public.transmodel_nonoperatingdatesexceptions owner to abods_rw;
CREATE INDEX ON public.transmodel_nonoperatingdatesexceptions (vehicle_journey_id);

create or replace procedure public.update_transmodel_nonoperatingdatesexceptions()
 LANGUAGE plpgsql
AS $procedure$
declare 
max_current int:= coalesce((select max(id) from public.transmodel_nonoperatingdatesexceptions), 0);
begin
insert into public.transmodel_nonoperatingdatesexceptions (
	id,
	non_operating_date,
	vehicle_journey_id
)
select
	id,
	non_operating_date,
	vehicle_journey_id
 from bods.transmodel_nonoperatingdatesexceptions tn
where tn.id > max_current
on conflict do nothing;
end; $procedure$
;
alter procedure public.update_transmodel_nonoperatingdatesexceptions owner to abods_rw;

-- Table: public.transmodel_operatingdatesexceptions

CREATE TABLE if not exists public.transmodel_operatingdatesexceptions (
	id bigint primary key,
	operating_date date NULL,
	vehicle_journey_id int4 NOT NULL
);
alter table public.transmodel_operatingdatesexceptions owner to abods_rw;
CREATE INDEX ON public.transmodel_operatingdatesexceptions (vehicle_journey_id);

create or replace procedure public.update_transmodel_operatingdatesexceptions()
 LANGUAGE plpgsql
AS $procedure$
declare 
max_current int:= coalesce((select max(id) from public.transmodel_operatingdatesexceptions), 0);
begin
insert into public.transmodel_operatingdatesexceptions (
	id,
	operating_date,
	vehicle_journey_id
)
select
	id,
	operating_date,
	vehicle_journey_id
 from bods.transmodel_operatingdatesexceptions too
where too.id > max_current
on conflict do nothing;
end; $procedure$
;
alter procedure public.update_transmodel_operatingdatesexceptions owner to abods_rw;

-- Table: public.transmodel_operatingprofile

CREATE TABLE if not exists public.transmodel_operatingprofile (
	id bigint primary key,
	day_of_week text NOT NULL,
	vehicle_journey_id int4 NOT NULL
);
alter table public.transmodel_operatingprofile owner to abods_rw;
CREATE INDEX ON public.transmodel_operatingprofile (vehicle_journey_id);

create or replace procedure public.update_transmodel_operatingprofile()
 LANGUAGE plpgsql
AS $procedure$
declare 
max_current int:= coalesce((select max(id) from public.transmodel_operatingprofile), 0);
begin
insert into public.transmodel_operatingprofile (
	id,
	day_of_week,
	vehicle_journey_id
)
select
	id,
	day_of_week,
	vehicle_journey_id
 from bods.transmodel_operatingprofile too
where too.id > max_current
on conflict do nothing;
end; $procedure$
;
alter procedure public.update_transmodel_operatingprofile owner to abods_rw;

-- Table: public.transmodel_service

CREATE TABLE if not exists public.transmodel_service (
	id bigint primary key,
	service_code text NOT NULL,
	"name" text NOT NULL,
	other_names _text NOT NULL,
	start_date date NOT NULL,
	end_date date NULL,
	revision_id int4 NULL,
	service_type text NOT NULL,
	txcfileattributes_id int4 NULL
);
alter table public.transmodel_service owner to abods_rw;
CREATE INDEX ON public.transmodel_service (revision_id);
CREATE INDEX ON public.transmodel_service (txcfileattributes_id);

create or replace procedure public.update_transmodel_service()
 LANGUAGE plpgsql
AS $procedure$
declare 
max_current int:= coalesce((select max(id) from public.transmodel_service), 0);
begin
insert into public.transmodel_service (
	id,
	service_code,
	"name",
	other_names,
	start_date,
	end_date,
	revision_id,
	service_type,
	txcfileattributes_id
)
select
	id,
	service_code,
	"name",
	other_names,
	start_date,
	end_date,
	revision_id,
	service_type,
	txcfileattributes_id
 from bods.transmodel_service ts
where ts.id > max_current
on conflict do nothing;
end; $procedure$
;
alter procedure public.update_transmodel_service owner to abods_rw;

-- Table: public.transmodel_service_service_patterns

CREATE TABLE if not exists public.transmodel_service_service_patterns (
	id bigint primary key,
	service_id int4 NOT NULL,
	servicepattern_id int4 NOT NULL
);
alter table public.transmodel_service_service_patterns owner to abods_rw;
CREATE INDEX ON public.transmodel_service_service_patterns (service_id);
CREATE index ON public.transmodel_service_service_patterns (servicepattern_id);

create or replace procedure public.update_transmodel_service_service_patterns()
 LANGUAGE plpgsql
AS $procedure$
declare 
max_current int:= coalesce((select max(id) from public.transmodel_service_service_patterns), 0);
begin
insert into public.transmodel_service_service_patterns (
	id,
	service_id,
	servicepattern_id
)
select
	id,
	service_id,
	servicepattern_id
 from bods.transmodel_service_service_patterns ts
where ts.id > max_current
on conflict do nothing;
end; $procedure$
;
alter procedure public.update_transmodel_service_service_patterns owner to abods_rw;

-- Table: public.transmodel_servicedorganisationvehiclejourney;

CREATE TABLE if not exists public.transmodel_servicedorganisationvehiclejourney (
	id bigint primary key,
	operating_on_working_days bool NOT NULL,
	serviced_organisation_id int4 NOT NULL,
	vehicle_journey_id int4 NOT NULL
);
alter table public.transmodel_servicedorganisationvehiclejourney owner to abods_rw;
CREATE INDEX ON public.transmodel_servicedorganisationvehiclejourney (serviced_organisation_id);
CREATE INDEX ON public.transmodel_servicedorganisationvehiclejourney (vehicle_journey_id);

create or replace procedure public.update_transmodel_servicedorganisationvehiclejourney()
 LANGUAGE plpgsql
AS $procedure$
declare 
max_current int:= coalesce((select max(id) from public.transmodel_servicedorganisationvehiclejourney), 0);
begin
insert into public.transmodel_servicedorganisationvehiclejourney (
	id,
	operating_on_working_days,
	serviced_organisation_id,
	vehicle_journey_id
)
select
	id,
	operating_on_working_days,
	serviced_organisation_id,
	vehicle_journey_id
 from bods.transmodel_servicedorganisationvehiclejourney ts
where ts.id > max_current
on conflict do nothing;
end; $procedure$
;
alter procedure public.update_transmodel_servicedorganisationvehiclejourney owner to abods_rw;

-- Table: public.transmodel_servicedorganisationworkingdays

CREATE TABLE if not exists public.transmodel_servicedorganisationworkingdays (
	id bigint primary key,
	start_date date NULL,
	end_date date NULL,
	serviced_organisation_vehicle_journey_id int4 NULL);
alter table public.transmodel_servicedorganisationworkingdays owner to abods_rw;
CREATE INDEX ON public.transmodel_servicedorganisationworkingdays (serviced_organisation_vehicle_journey_id);

create or replace procedure public.update_transmodel_servicedorganisationworkingdays()
 LANGUAGE plpgsql
AS $procedure$
declare 
max_current int:= coalesce((select max(id) from public.transmodel_servicedorganisationworkingdays), 0);
begin
insert into public.transmodel_servicedorganisationworkingdays (
	id,
	start_date,
	end_date,
	serviced_organisation_vehicle_journey_id
)
select
	id,
	start_date,
	end_date,
	serviced_organisation_vehicle_journey_id
 from bods.transmodel_servicedorganisationworkingdays ts
where ts.id > max_current
on conflict do nothing;
end; $procedure$
;
alter procedure public.update_transmodel_servicedorganisationworkingdays owner to abods_rw;

-- Table: public.transmodel_vehiclejourney

CREATE TABLE if not exists public.transmodel_vehiclejourney (
	id bigint primary key,
	start_time time NULL,
	direction text NULL,
	journey_code text NULL,
	line_ref text NULL,
	departure_day_shift bool NOT NULL,
	service_pattern_id int4 NULL,
	block_number int4 NULL
);
alter table public.transmodel_vehiclejourney owner to abods_rw;
CREATE INDEX ON public.transmodel_vehiclejourney (service_pattern_id);

create or replace procedure public.update_transmodel_vehiclejourney()
 LANGUAGE plpgsql
AS $procedure$
declare 
max_current int:= coalesce((select max(id) from public.transmodel_vehiclejourney), 0);
begin
insert into public.transmodel_vehiclejourney (
	id,
	start_time,
	direction,
	journey_code,
	line_ref,
	departure_day_shift,
	service_pattern_id,
	block_number
)
select
	id,
	start_time,
	direction,
	journey_code,
	line_ref,
	departure_day_shift,
	service_pattern_id,
	block_number
 from bods.transmodel_vehiclejourney tvj
where tvj.id > max_current
on conflict do nothing;
end; $procedure$
;
alter procedure public.update_transmodel_vehiclejourney owner to abods_rw;

-- Table: public.naptan_adminarea

CREATE TABLE if not exists public.naptan_adminarea (
	id bigint primary key,
	"name" text NOT NULL,
	traveline_region_id text NOT NULL,
	atco_code text NOT NULL,
	ui_lta_id int4 NULL
);
alter table public.naptan_adminarea owner to abods_rw;
CREATE INDEX ON public.naptan_adminarea (atco_code varchar_pattern_ops);

create or replace procedure public.update_naptan_adminarea()
 LANGUAGE plpgsql
AS $procedure$
begin
insert into public.naptan_adminarea (
	id,
	"name",
	traveline_region_id,
	atco_code,
	ui_lta_id
)
select
	id,
	"name",
	traveline_region_id,
	atco_code,
	ui_lta_id
 from bods.naptan_adminarea na
on conflict (id)
do update set ("name", traveline_region_id, atco_code, ui_lta_id) = (EXCLUDED."name", EXCLUDED.traveline_region_id, EXCLUDED.atco_code, EXCLUDED.ui_lta_id);
end; $procedure$
;
alter procedure public.update_transmodel_vehiclejourney owner to abods_rw;

-- Table: public.naptan_locality;
CREATE table if not exists public.naptan_locality (
	gazetteer_id text primary key,
	"name" text NOT NULL,
	easting int4 NOT NULL,
	northing int4 NOT NULL,
	admin_area_id int4 NULL,
	district_id int4 null
);
CREATE INDEX ON public.naptan_locality (admin_area_id);
CREATE INDEX ON public.naptan_locality (district_id);
CREATE INDEX ON public.naptan_locality (gazetteer_id varchar_pattern_ops);

create or replace procedure public.update_naptan_locality()
 LANGUAGE plpgsql
AS $procedure$
begin
insert into public.naptan_locality (
	gazetteer_id,
	"name",
	easting,
	northing,
	admin_area_id,
	district_id
)
select
	gazetteer_id,
	"name",
	easting,
	northing,
	admin_area_id,
	district_id
 from bods.naptan_locality nl
on conflict (gazetteer_id)
do update set ("name", easting, northing, admin_area_id, district_id) = (EXCLUDED."name", EXCLUDED.easting, EXCLUDED.northing, EXCLUDED.admin_area_id, EXCLUDED.district_id);
end; $procedure$
;
alter procedure public.update_naptan_locality owner to abods_rw;

-- Table: public.naptan_stoppoint
CREATE TABLE if not exists public.naptan_stoppoint (
	id bigint primary key,
	atco_code text NOT NULL,
	naptan_code text NULL,
	common_name text NOT NULL,
	street text NULL,
	"indicator" text NULL,
	"location" public.geometry(point, 4326) NOT NULL,
	admin_area_id int4 NULL,
	locality_id text NULL,
	stop_areas _text NOT NULL,
	bus_stop_type text NULL,
	stop_type text NULL
);
CREATE INDEX ON public.naptan_stoppoint(admin_area_id);
CREATE INDEX ON public.naptan_stoppoint (atco_code varchar_pattern_ops);
CREATE INDEX ON public.naptan_stoppoint (locality_id);
CREATE INDEX ON public.naptan_stoppoint (locality_id varchar_pattern_ops);

create or replace procedure public.update_naptan_stoppoint()
 LANGUAGE plpgsql
AS $procedure$
begin
insert into public.naptan_stoppoint (
	id,
	atco_code,
	naptan_code,
	common_name,
	street,
	"indicator",
	"location",
	admin_area_id,
	locality_id,
	stop_areas,
	bus_stop_type,
	stop_type
)
select
	id,
	atco_code,
	naptan_code,
	common_name,
	street,
	"indicator",
	"location",
	admin_area_id,
	locality_id,
	stop_areas,
	bus_stop_type,
	stop_type
 from bods.naptan_stoppoint ns
on conflict (id)
do update set (
		atco_code,
		naptan_code,
		common_name,
		street,
		"indicator",
		"location",
		admin_area_id,
		locality_id,
		stop_areas,
		bus_stop_type,
		stop_type
	) = (
		EXCLUDED.atco_code,
		EXCLUDED.naptan_code,
		EXCLUDED.common_name,
		EXCLUDED.street,
		EXCLUDED."indicator",
		EXCLUDED."location",
		EXCLUDED.admin_area_id,
		EXCLUDED.locality_id,
		EXCLUDED.stop_areas,
		EXCLUDED.bus_stop_type,
		EXCLUDED.stop_type
	);
end; $procedure$
;
alter procedure public.update_naptan_stoppoint owner to abods_rw;

-- Procedure: public.update_all_transmodel_tables()

create or replace procedure public.update_all_transmodel_tables()
 LANGUAGE plpgsql
AS $procedure$
begin
raise notice 'Running update_transmodel_servicepattern at %', current_timestamp;
call public.update_transmodel_servicepattern();
commit;
raise notice 'Running update_transmodel_servicepatternstop at %', current_timestamp;
call public.update_transmodel_servicepatternstop();
commit;
raise notice 'Running update_organisation_datasetrevision at %', current_timestamp;
call public.update_organisation_datasetrevision();
commit;
raise notice 'Running update_organisation_txcfileattributes at %', current_timestamp;
call public.update_organisation_txcfileattributes();
commit;
raise notice 'Running update_transmodel_nonoperatingdatesexceptions at %', current_timestamp;
call public.update_transmodel_nonoperatingdatesexceptions();
commit;
raise notice 'Running update_transmodel_operatingdatesexceptions at %', current_timestamp;
call public.update_transmodel_operatingdatesexceptions();
commit;
raise notice 'Running update_transmodel_operatingprofile at %', current_timestamp;
call public.update_transmodel_operatingprofile();
commit;
raise notice 'Running update_transmodel_service at %', current_timestamp;
call public.update_transmodel_service();
commit;
raise notice 'Running update_transmodel_service_service_patterns at %', current_timestamp;
call public.update_transmodel_service_service_patterns();
commit;
raise notice 'Running update_transmodel_servicedorganisationvehiclejourney at %', current_timestamp;
call public.update_transmodel_servicedorganisationvehiclejourney();
commit;
raise notice 'Running update_transmodel_servicedorganisationworkingdays at %', current_timestamp;
call public.update_transmodel_servicedorganisationworkingdays();
commit;
raise notice 'Running update_transmodel_vehiclejourney at %', current_timestamp;
call public.update_transmodel_vehiclejourney();
commit;
end; $procedure$
;
alter procedure public.update_all_transmodel_tables owner to abods_rw;

-- Procedure: procedure public.update_all_naptan_tables()

create or replace procedure public.update_all_naptan_tables()
 LANGUAGE plpgsql
AS $procedure$
begin
raise notice 'Running update_naptan_adminarea at %', current_timestamp;
call public.update_naptan_adminarea();
commit;
raise notice 'Running update_naptan_locality at %', current_timestamp;
call public.update_naptan_locality();
commit;
raise notice 'Running update_naptan_stoppoint at %', current_timestamp;
call public.update_naptan_stoppoint();
commit;
end; $procedure$
;
alter procedure public.update_all_naptan_tables owner to abods_rw;

-- Table: public."Timetable"

CREATE TABLE IF NOT EXISTS public."Timetable"
	(
	    timetable_id bigserial,
	    operator_noc text NOT NULL,
	    operator_name text NOT NULL,
	    service_code text NOT NULL,
	    line_name text,
	    xml_file_name text,
	    journey_code text,
	    date_of_journey date NOT NULL,
	    day_of_week int,
	    common_name text,
	    atco_code text,
	    stop_type text,
	    stop_index int,
	    stop_latitude real,
	    stop_longitude real,
	    locality_id text,
	    expected_departure_time time without time zone,
	    actual_departure_time time without time zone,
	    is_timing_point boolean,
	    group_id text,
	    previous_group_id text,
	    otp_state text,
	    expected_headway int,
	    actual_headway int,
	    headway_time_difference int,
	    siri_vm_position_id bigint,
	    time_difference int,
	    stop_id bigint,
		load_time_stamp timestamp DEFAULT now() NULL,
	    CONSTRAINT timetable_pk_240603 PRIMARY KEY (timetable_id, date_of_journey)
	)
PARTITION BY RANGE (date_of_journey);
ALTER TABLE public."Timetable" OWNER to abods_rw;

--------------------------------
-- Create timetable generator --
--------------------------------
CREATE OR REPLACE PROCEDURE public.generate_timetable(partition_date date)
 LANGUAGE plpgsql
AS $procedure$

declare 
longdatestring text:= to_char(partition_date, 'YYYY_MM_DD');
timetable_suffix text:= concat('_', longdatestring);
tablename text:= 'Timetable';

begin

RAISE NOTICE '(Re)Creating organisation_timetable temp table';

execute format(
'drop table if exists public.%I', 
concat('organisation_timetable', timetable_suffix)
);

execute format(
'create table public.%I as 
	WITH FilteredFiles AS (
		SELECT
			a.id as txcfileattributes_id,
	        a.national_operator_code,
	        a.service_code,
	        a.line_names  as line_name,
	        a.filename,
	        a.revision_number,
			a.revision_id,
	        a.operating_period_start_date,
	        a.operating_period_end_date
	    FROM
	        public.organisation_txcfileattributes a
	        join public.organisation_datasetrevision od
			on od.id = a.revision_id
	    WHERE
			%L BETWEEN operating_period_start_date AND coalesce (operating_period_end_date,''2050-12-31''::date)
	        and operating_period_start_date > ''2023-06-01''::date 
			and od.is_published is true 
			and od.status = ''live''	
	),
	
	MaxRevisionFiles AS (
	    SELECT
	        national_operator_code,
	        service_code,
	        line_name,
	        --revision_number AS revision_number,
			MAX(revision_id) AS MaxRevisionid
			
	    FROM
	        FilteredFiles
	    GROUP BY
	        national_operator_code, service_code, line_name
	),
	MaxStartDates as (
		select 
			x.national_operator_code,
			x.service_code,
			x.line_names,
			max(x.operating_period_start_date) as max_date
		from organisation_txcfileattributes x
			    where x.operating_period_start_date > %L
		group by 
			x.national_operator_code,
			x.service_code,
			x.line_names

	)
	
	SELECT distinct 
		f.txcfileattributes_id,
	    f.national_operator_code,
	    f.service_code,
	    f.line_name,
		f.filename,
	    f.revision_id,
		f.revision_number
	FROM
	    MaxRevisionFiles m
	JOIN
	    FilteredFiles f
	    ON m.national_operator_code = f.national_operator_code
	    AND m.service_code = f.service_code
	    AND m.line_name = f.line_name
	    AND m.MaxRevisionid = f.revision_id
	left join MaxStartDates msd
		on f.national_operator_code = msd.national_operator_code
		and f.service_code = msd.service_code
		and f.line_name = msd.line_names
	WHERE
	    msd.max_date is null
	ORDER BY
	    f.national_operator_code, f.service_code, f.line_name',
concat('organisation_timetable', timetable_suffix),
partition_date,
partition_date
);

RAISE NOTICE '(Re)Creating timetable_vehiclejourney temp table';

execute format(
'drop table if exists public.%I',
concat('timetable_vehiclejourney', timetable_suffix)
);

execute format(
'create table public.%I as    
	select 
		a.*,
		tv.*,
		%L::date as date_of_journey,
		ts2.line_name as exploded_line_name
	from public.%I a
	join public.transmodel_service ts
	on a.revision_id=ts.revision_id 
	and a.txcfileattributes_id=ts.txcfileattributes_id 
	and %L between ts.start_date and coalesce(ts.end_date,''2050-12-31''::date)
   
   join public.transmodel_service_service_patterns tssp 
   on ts.id =  tssp.service_id 
   
   join public.transmodel_servicepattern ts2 
   on tssp.servicepattern_id =ts2.id
   
   join public.transmodel_vehiclejourney tv 
   on ts2.id = tv.service_pattern_id',
concat('timetable_vehiclejourney', timetable_suffix),
partition_date,
concat('organisation_timetable', timetable_suffix),
partition_date
);

RAISE NOTICE '(Re)Creating timetable_vehiclejourney_workingdays temp table';

execute format (
'drop table if exists public.%I',
concat('timetable_vehiclejourney_workingdays', timetable_suffix)
);

execute format (
'create table public.%I as     
 	select tv.* from 
	public.%I tv 
 	left join (
		select tv.id, 
 		MAX(
			case 
				when current_date between tsw.start_date and tsw.end_date and ts.operating_on_working_days is true 
      			then ''yes''
      			when current_date not between tsw.start_date and tsw.end_date and ts.operating_on_working_days is false 
      			then ''yes''
      			else ''no''
      		end
		) as flag 
 		from public.%I tv 
 
 		join public.transmodel_servicedorganisationvehiclejourney ts 
 		on tv.id = ts.vehicle_journey_id
 
		join public.transmodel_servicedorganisationworkingdays tsw
		on ts.id  = tsw.serviced_organisation_vehicle_journey_id  
 
		group by tv.id
 	) workingday on 
 
 	tv.id = workingday.id 

	where coalesce(workingday.flag,''yes'') = ''yes''
	',
concat('timetable_vehiclejourney_workingdays', timetable_suffix),
concat('timetable_vehiclejourney', timetable_suffix),
concat('timetable_vehiclejourney', timetable_suffix)
);

RAISE NOTICE '(Re)Creating timetable_vehiclejourney_exclusions temp table';

execute format (
'drop table if exists public.%I',
concat('timetable_vehiclejourney_exclusions', timetable_suffix)
);

execute format (
'create table public.%I as     
		select id from (
			select tvw.id,
			MIN(
				case
					when tne.vehicle_journey_id is not null and toe.operating_date = current_date 
         			then 1 -- include 
	   				when top.vehicle_journey_id is not null and  top.day_of_week = to_char(now(), ''Day'')
       				then 1 -- include 
       				when tne.vehicle_journey_id is not null and tne.non_operating_date = current_date 
       				then 0 -- exclude 
       				else null 
      			end
			) flag 
 		from public.%I tvw 

 		left join public.transmodel_operatingprofile top 
		on tvw.id =top.vehicle_journey_id 

		left join public.transmodel_nonoperatingdatesexceptions tne 
		on tvw.id = tne.vehicle_journey_id

		left join public.transmodel_operatingdatesexceptions toe
		on tvw.id = toe.vehicle_journey_id
 
		group by 1 
 	) x 
 	where x.flag=0',
concat('timetable_vehiclejourney_exclusions', timetable_suffix),
concat('timetable_vehiclejourney_workingdays', timetable_suffix)
);

RAISE NOTICE '(Re)Creating timetable_journey temp table';

execute format (
'drop table if exists public.%I',
concat('timetable_journey', timetable_suffix)
);

execute format (
'create table public.%I as 
 	select 
 		national_operator_code as operator,
		service_code,
		exploded_line_name as line_name,
		'''' as description,
		filename as file_name,
		journey_code,
		date_of_journey,
		extract(dow from date_of_journey) as day_of_week,
		coalesce(stop.naptan_stop_id::text,'''') as stop_id,
		stop.sequence_number  as stop_index,
		stop.departure_time as departure_time,
		stop.is_timing_point as is_timing_point,
		'' '' as group_id,
		tvw.id as transmodel_vehiclejourney_id,
		tvw.service_pattern_id as transmodel_servicepattern_id,
		stop.atco_code
	from public.%I tvw 
	join public.transmodel_servicepatternstop stop 
 	on tvw.id = stop.vehicle_journey_id 
 	where tvw.id not in (
		select id from public.%I
	)
 	and trim(tvw.journey_code) <> ''''
 	',
concat('timetable_journey', timetable_suffix),
concat('timetable_vehiclejourney_workingdays', timetable_suffix),
concat('timetable_vehiclejourney_exclusions', timetable_suffix)
);

RAISE NOTICE '(Re)Creating timetable_stop temp table';

execute format (
'drop table if exists public.%I',
concat('timetable_stop', timetable_suffix)
);

execute format (
'create table public.%I as 
	select 
		"operator" as operator_ref,
		line_name,
		journey_code,
		date_of_journey as date_of_journey,
		departure_time,
		stop_id,
		ST_Y(b.location)::real lt,
		ST_X(b.location)::real as lon,
		common_name as stopname,
		a.stop_index,
		b.common_name as stop_name
		,a.is_timing_point,
		b.locality_id,
		service_code,
		file_name as filename,
		day_of_week,
		stop_type,
		concat("operator",line_name,journey_code,date_of_journey) as group_id,
		a.atco_code,
		row_number() over(partition by "operator",line_name,journey_code,date_of_journey,stop_id order by file_name ) as rk 	
	from public.%I a
	join public.naptan_stoppoint b
	on a.stop_id  = b.id::text
	',
concat('timetable_stop', timetable_suffix),
concat('timetable_journey', timetable_suffix)
);

----------------------------
-- Create dated partition --
----------------------------

RAISE NOTICE '(Re)Creating partition';


execute format(
'CREATE TABLE if not exists public.%I partition of public.%I FOR VALUES FROM (%L) TO (%L)',
concat( tablename, '_p', longdatestring),
tablename,
partition_date,
partition_date + interval '1' day);

execute format('
	ALTER TABLE public.%I OWNER to abods_rw',
	concat( tablename, '_p', longdatestring)
);

commit;

------------------------------
-- Deleting from partition --
------------------------------

RAISE NOTICE 'Deleting from partition';

execute format(
	'DELETE FROM public.%I',
	concat( tablename, '_p', longdatestring)
);

----------------------------
-- Importing to partition --
----------------------------

RAISE NOTICE 'Inserting into partition';

execute format(
'Insert into public.%I (
		operator_noc,
		operator_name,
		service_code,
		line_name,
		xml_file_name,
		journey_code,
		date_of_journey,
		day_of_week,
		common_name,
		atco_code,
		stop_type,
		stop_index,
		stop_latitude,
		stop_longitude,
		locality_id,
		expected_departure_time,
		actual_departure_time,
		is_timing_point,
		group_id,
		previous_group_id,
		otp_state,
		expected_headway,
		actual_headway,
		headway_time_difference,
		siri_vm_position_id,
		time_difference,
		stop_id
	)
 
	select 
		operator_ref as operator_noc,
		'''' as operator_name,
		service_code,
		line_name,
		filename as xml_file_name,
		journey_code,
		date_of_journey,
		day_of_week,
		stop_name as common_name,
		atco_code as atco_code,
		stop_type,
		stop_index,
		lt as stop_latitude,
		lon as stop_longitude,
		locality_id,
		departure_time as expected_departure_time,
		null as actual_departure_time,
		is_timing_point,
		group_id as group_id,
		lag(group_id) over(partition by operator_ref,line_name,date_of_journey,stop_id,stop_index  order by stop_id,stop_index, departure_time  asc  )  as previous_group_id,
		null as otp_state,
		cast(extract( epoch from departure_time::time - lag(departure_time::time) over(partition by operator_ref,line_name,date_of_journey,stop_id,stop_index  order by stop_id,stop_index, departure_time  asc  ) )/60 as int) as expected_headway,
		null as actual_headway,
		null as headway_time_difference,
		null as siri_vm_position_id,
		null as time_difference,
		nullif(stop_id,'''')::int

	from public.%I x 

	where rk=1',
concat( tablename, '_p', longdatestring),
concat('timetable_stop', timetable_suffix)
);

--------------
-- Clean Up --
--------------

RAISE NOTICE 'Cleaning Up';


execute format(
'drop table if exists public.%I', 
concat('organisation_timetable', timetable_suffix)
);

execute format(
'drop table if exists public.%I',
concat('timetable_vehiclejourney', timetable_suffix)
);

execute format (
'drop table if exists public.%I',
concat('timetable_vehiclejourney_workingdays', timetable_suffix)
);

execute format (
'drop table if exists public.%I',
concat('timetable_vehiclejourney_exclusions', timetable_suffix)
);

execute format (
'drop table if exists public.%I',
concat('timetable_journey', timetable_suffix)
);

execute format (
'drop table if exists public.%I',
concat('timetable_stop', timetable_suffix)
);


end; $procedure$
;
