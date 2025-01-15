create or replace procedure update_all_transmodel_tables()
    language plpgsql
as
$$
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
end;
$$;

alter procedure update_all_transmodel_tables owner to abods_proxy_rw;
