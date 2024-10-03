CREATE TABLE if not exists public.expected_journeys (
	date_of_journey date,
	operator_noc text,
	line_name text,
	noc_and_line text,
	journey_code text,
	group_id text,
	stop_count int4,
	expected_journey_start time with time zone,
	journey_pattern_description text,
	vehicle_journey_id int4,
	day_of_week int4
);
ALTER TABLE public.expected_journeys owner to abods_rw;
CREATE index if not exists expected_journeys_date_of_journey_idx ON public.expected_journeys USING btree (date_of_journey);
CREATE INDEX if not exists expected_journeys_group_id_idx ON public.expected_journeys USING btree (group_id);
CREATE INDEX if not exists expected_journeys_operator_noc_line_name_journey_code_idx ON public.expected_journeys USING btree (operator_noc, line_name, journey_code);
CREATE INDEX if not exists expected_journeys_noc_and_line_idx ON public.expected_journeys USING btree (noc_and_line);

CREATE TABLE if not exists public.expected_services (
	date_of_journey date,
	operator_noc text,
	line_name text,
	noc_and_line text,
	service_name text
);
alter table public.expected_services owner to abods_rw;
CREATE INDEX if not exists expected_services_date_of_journey_idx ON public.expected_services USING btree (date_of_journey);
CREATE INDEX if not exists expected_services_operator_noc_line_name_idx ON public.expected_services USING btree (operator_noc, line_name);

CREATE TABLE if not exists public.expected_operators (
	date_of_journey date,
	operator_noc text,
	operator_name text
);
alter table public.expected_operators owner to abods_rw;
CREATE INDEX if not exists expected_operatorss_date_of_journey_idx ON public.expected_operators USING btree (date_of_journey);
CREATE INDEX if not exists expected_operators_operator_noc_idx ON public.expected_operators USING btree (operator_noc);


CREATE OR REPLACE PROCEDURE public.generate_expected_tables(IN partition_date date)
 LANGUAGE plpgsql
AS $procedure$
begin
RAISE NOTICE 'Deleting expected journeys for %', partition_date::text ;

delete from expected_journeys where date_of_journey = partition_date;

RAISE NOTICE 'Inserting expected journeys for for %', partition_date::text ;

insert into expected_journeys (
	date_of_journey,
	operator_noc,
	line_name,
	noc_and_line,
	journey_code,
	group_id,
	stop_count,
	expected_journey_start,
	journey_pattern_description,
	vehicle_journey_id,
	day_of_week
)
select distinct
	t.date_of_journey,
	t.operator_noc,
	t.line_name,
	concat(t.operator_noc, '-', t.line_name) as noc_and_line,
	t.journey_code,
	t.group_id,
	count(stop_index) over w as stop_count,
	first_value(t.expected_departure_time::timetz) over w as start_time,
	ts.description as journey_pattern_description,
	t.vehiclejourney_id,
	t.day_of_week
from "Timetable" t
left join transmodel_servicepattern ts 
on t.servicepattern_id = ts.id
where t.date_of_journey = partition_date
window w as (
	partition by t.group_id 
	order by t.stop_index asc 
	range between unbounded preceding and unbounded following
)
;

RAISE NOTICE 'Analysing expected journeys for for %', partition_date::text ;

analyse expected_journeys;

RAISE NOTICE 'Deleting expected services for for %', partition_date::text ;

delete from expected_services where date_of_journey = partition_date;

RAISE NOTICE 'Inserting expected services for for %', partition_date::text ;

insert into expected_services (
	date_of_journey,
	operator_noc,
	line_name,
	noc_and_line,
	service_name
)
select distinct
date_of_journey,
operator_noc,
line_name,
noc_and_line,
first_value(journey_pattern_description) over (partition by date_of_journey, operator_noc, line_name order by stop_count desc, journey_pattern_description asc) as service_name
from expected_journeys
where date_of_journey = partition_date;

RAISE NOTICE 'Analysing expected services for for %', partition_date::text ;

analyse expected_services;

RAISE NOTICE 'Deleting expected operators for for %', partition_date::text ;

delete from expected_operators where date_of_journey = partition_date;

RAISE NOTICE 'Inserting expected operators for for %', partition_date::text ;

insert into expected_operators (
	date_of_journey,
	operator_noc,
	operator_name
)
select distinct es.date_of_journey, es.operator_noc, o."name"
from expected_services es
left join traveline_operators o on
o.noc_code = es.operator_noc
where es.date_of_journey = partition_date;

RAISE NOTICE 'Analysing expected operators for for %', partition_date::text ;

analyse expected_operators;

RAISE NOTICE 'Done';

end; $procedure$
;

ALTER PROCEDURE public.generate_expected_tables owner to abods_rw;

select cron.schedule('generate timetable', '05 15 * * *',  $$call update_all_transmodel_tables(); call update_all_naptan_tables(); call generate_timetable(current_date + 1); call generate_expected_tables(current_date + 1);$$);

IMPORT FOREIGN SCHEMA public LIMIT TO (
    organisation_dataset
)
FROM SERVER bods INTO bods;

CREATE TABLE if not exists public.organisation_dataset (
	id int4 primary key,
	created timestamptz,
	modified timestamptz,
	live_revision_id int4,
	organisation_id int,
	contact_id int4,
	dataset_type int4,
	avl_feed_status text,
	avl_feed_last_checked timestamptz,
	is_dummy bool
);
alter table public.organisation_dataset owner to abods_rw;
CREATE INDEX  if not exists organisation_dataset_organisation_id_idx ON public.organisation_dataset (organisation_id);

CREATE OR REPLACE PROCEDURE public.update_organisation_dataset()
 LANGUAGE plpgsql
AS $procedure$
declare 
max_current int := coalesce((
select
	max(id)
from
	public.organisation_dataset),
0);

begin
insert
	into
	public.organisation_dataset (
	id,
	created,
	modified,
	live_revision_id,
	organisation_id,
	contact_id,
	dataset_type,
	avl_feed_status,
	avl_feed_last_checked,
	is_dummy
)
select
	id,
	created,
	modified,
	live_revision_id,
	organisation_id,
	contact_id,
	dataset_type,
	avl_feed_status,
	avl_feed_last_checked,
	is_dummy
from
	bods.organisation_dataset od
on
	conflict (id) do update set (
		created,
		modified,
		live_revision_id,
		organisation_id,
		contact_id,
		dataset_type,
		avl_feed_status,
		avl_feed_last_checked,
		is_dummy
	) = (
		EXCLUDED.created,
		EXCLUDED.modified,
		EXCLUDED.live_revision_id,
		EXCLUDED.organisation_id,
		EXCLUDED.contact_id,
		EXCLUDED.dataset_type,
		EXCLUDED.avl_feed_status,
		EXCLUDED.avl_feed_last_checked,
		EXCLUDED.is_dummy	
	)
;
end;

$procedure$
;

alter procedure public.update_organisation_dataset owner to abods_rw;


CREATE OR REPLACE PROCEDURE public.update_organisation_datasetrevision()
 LANGUAGE plpgsql
AS $procedure$
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
on conflict (id) do update set (
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
)=(
	EXCLUDED.created,
	EXCLUDED.modified,
	EXCLUDED.upload_file,
	EXCLUDED.status,
	EXCLUDED."name",
	EXCLUDED.description,
	EXCLUDED."comment",
	EXCLUDED.is_published,
	EXCLUDED.url_link,
	EXCLUDED.num_of_lines,
	EXCLUDED.num_of_operators,
	EXCLUDED.transxchange_version,
	EXCLUDED.imported,
	EXCLUDED.bounding_box,
	EXCLUDED.publisher_creation_datetime,
	EXCLUDED.publisher_modified_datetime,
	EXCLUDED.first_expiring_service,
	EXCLUDED.last_expiring_service,
	EXCLUDED.first_service_start,
	EXCLUDED.num_of_bus_stops,
	EXCLUDED.dataset_id,
	EXCLUDED.last_modified_user_id,
	EXCLUDED.published_by_id,
	EXCLUDED.published_at,
	EXCLUDED."password",
	EXCLUDED.requestor_ref,
	EXCLUDED.username,
	EXCLUDED.short_description,
	EXCLUDED.num_of_timing_points
);
end; $procedure$
;

alter procedure public.update_organisation_datasetrevision owner to abods_rw;

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
end; $procedure$
;

alter procedure public.update_all_transmodel_tables owner to abods_rw;

create or replace view public.naptan_stoppoint_latlong as
select
	id,
	atco_code,
	naptan_code,
	common_name,
	street,
	"indicator",
	admin_area_id,
	locality_id,
	stop_areas,
	bus_stop_type,
	stop_type,
	ST_X("location") as longitude, ST_Y("location") as latitude
from
	public.naptan_stoppoint;

alter view public.naptan_stoppoint_latlong owner to abods_rw;