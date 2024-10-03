alter table public."Timetable"
        alter column expected_departure_time type timestamptz
        using (date_of_journey + expected_departure_time) at TIME zone 'Europe/London', 
        alter column actual_departure_time type timestamptz
        using (date_of_journey + actual_departure_time) at TIME zone 'Europe/London';

alter table "SiriVMPositions"
alter column recorded_at_time type timestamptz
using recorded_at_time at TIME zone 'utc',
alter column response_time_stamp type timestamptz
using recorded_at_time at TIME zone 'utc',
alter column load_time_stamp type timestamptz
using recorded_at_time at TIME zone 'utc';

alter table if exists partman."template_public_SiriVMPositions"
alter column recorded_at_time type timestamptz,
alter column response_time_stamp type timestamptz,
alter column load_time_stamp type timestamptz;

CREATE OR REPLACE VIEW public.bods_organisation_organisation_admin_areas
AS
SELECT id, organisation_id, adminarea_id
FROM bods.organisation_organisation_admin_areas;

CREATE TABLE IF NOT EXISTS public.transmodel_servicepattern_admin_areas (
	id int4 primary key,
	servicepattern_id int4 NOT NULL,
	adminarea_id int4  NOT NULL
);
ALTER TABLE public.transmodel_servicepattern_admin_areas  owner to abods_rw;
CREATE INDEX IF NOT EXISTS transmodel_servicepattern_admin_areas_servicepattern_id ON public.transmodel_servicepattern_admin_areas USING btree (servicepattern_id);
CREATE INDEX IF NOT EXISTS transmodel_servicepattern_admin_areas_adminarea_id ON public.transmodel_servicepattern_admin_areas USING btree (adminarea_id);

create or replace procedure public.update_transmodel_servicepattern_admin_areas()
 LANGUAGE plpgsql
AS $procedure$
declare 
max_current int:= coalesce((select max(id) from public.transmodel_servicepattern_admin_areas), 0);
begin
insert into public.transmodel_servicepattern_admin_areas (
	id,
	servicepattern_id,
	adminarea_id
)
select
	id,
	servicepattern_id,
	adminarea_id
 from bods.transmodel_servicepattern_admin_areas tsaa
where tsaa.id > max_current
on conflict do nothing;
end; $procedure$
;
alter procedure public.update_transmodel_servicepattern_admin_areas owner to abods_rw;

drop view if exists public.bods_organisationoperator;
drop view if exists public.noc_adminarea;

CREATE MATERIALIZED VIEW if not exists public.noc_adminarea
AS SELECT ot.national_operator_code,
    tsas.adminarea_id
   FROM transmodel_servicepattern_admin_areas tsas
     JOIN transmodel_servicepattern ts ON tsas.servicepattern_id = ts.id
     JOIN transmodel_service_service_patterns tssp ON ts.id = tssp.servicepattern_id
     JOIN transmodel_service ts2 ON tssp.service_id = ts2.id
     JOIN organisation_txcfileattributes ot ON ot.id = ts2.txcfileattributes_id
  GROUP BY ot.national_operator_code, tsas.adminarea_id
WITH DATA;
alter MATERIALIZED VIEW public.noc_adminarea owner to abods_rw;

select cron.schedule('Refresh noc_adminarea materialized view', '05 03 * * *',  $$refresh MATERIALIZED VIEW public.noc_adminarea; $$);

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
end; $procedure$
;

CREATE OR REPLACE VIEW public.bods_organisationoperator
AS SELECT oo.organisation_id,
    oo.noc AS operatorref
   FROM bods_organisation bo
     LEFT JOIN bods.organisation_operatorcode oo ON bo.id = oo.organisation_id
  GROUP BY oo.organisation_id, oo.noc
UNION
 SELECT bo.id AS organisation_id,
    ao.operatorref
   FROM bods_organisation bo
     CROSS JOIN all_operators ao
  WHERE bo.is_abods_global_viewer = true
  GROUP BY bo.id, ao.operatorref
UNION
 SELECT bo.id AS organisation_id,
    na.national_operator_code AS operatorref
   FROM bods_organisation bo
     RIGHT JOIN bods.organisation_organisation_admin_areas ooaa ON bo.id = ooaa.organisation_id
     LEFT JOIN noc_adminarea na ON na.adminarea_id = ooaa.adminarea_id
  GROUP BY bo.id, na.national_operator_code;
alter VIEW public.bods_organisationoperator owner to abods_rw;