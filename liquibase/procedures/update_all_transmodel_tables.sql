create or replace procedure update_all_transmodel_tables()
    language plpgsql
as
$$
begin
    raise notice 'Running update_transmodel_servicepattern at %', clock_timestamp();
    call public.update_transmodel_servicepattern();
    raise notice 'Running update_transmodel_servicepatternstop at %', clock_timestamp();
    call public.update_transmodel_servicepatternstop();
    raise notice 'Running update_organisation_datasetrevision at %', clock_timestamp();
    call public.update_organisation_datasetrevision();
    raise notice 'Running update_organisation_txcfileattributes at %', clock_timestamp();
    call public.update_organisation_txcfileattributes();
    raise notice 'Running update_transmodel_nonoperatingdatesexceptions at %', clock_timestamp();
    call public.update_transmodel_nonoperatingdatesexceptions();
    raise notice 'Running update_transmodel_operatingdatesexceptions at %', clock_timestamp();
    call public.update_transmodel_operatingdatesexceptions();
    raise notice 'Running update_transmodel_operatingprofile at %', clock_timestamp();
    call public.update_transmodel_operatingprofile();
    raise notice 'Running update_transmodel_service at %', clock_timestamp();
    call public.update_transmodel_service();
    raise notice 'Running update_transmodel_service_service_patterns at %', clock_timestamp();
    call public.update_transmodel_service_service_patterns();
    raise notice 'Running update_transmodel_servicedorganisationvehiclejourney at %', clock_timestamp();
    call public.update_transmodel_servicedorganisationvehiclejourney();
    raise notice 'Running update_transmodel_servicedorganisationworkingdays at %', clock_timestamp();
    call public.update_transmodel_servicedorganisationworkingdays();
    raise notice 'Running update_transmodel_vehiclejourney at %', clock_timestamp();
    call public.update_transmodel_vehiclejourney();
    raise notice 'Running update_organisation_dataset at %', clock_timestamp();
    call public.update_organisation_dataset();
    raise notice 'Running update_transmodel_servicepattern_admin_areas at %', clock_timestamp();
    call public.update_transmodel_servicepattern_admin_areas();
    raise notice 'Running update_transmodel_tracks at %', clock_timestamp();
    call public.update_transmodel_tracks();
end;
$$;

alter procedure update_all_transmodel_tables owner to abods_proxy_rw;
