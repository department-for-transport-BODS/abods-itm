CREATE OR REPLACE PROCEDURE public.update_organisation_datasetrevision()
 LANGUAGE plpgsql
AS $procedure$
begin

--- Update for migration changeset 40 ---
delete from public.organisation_datasetrevision;
--- End update for migration changeset 40 ---

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
 from bods.organisation_datasetrevision
end; $procedure$
;

alter procedure public.update_organisation_datasetrevision owner to abods_rw;
