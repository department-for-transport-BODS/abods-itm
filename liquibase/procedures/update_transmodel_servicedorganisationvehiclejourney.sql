create or replace procedure update_transmodel_servicedorganisationvehiclejourney()
    language plpgsql
as
$$
declare
    max_current int := coalesce((select max(id)
                                 from public.transmodel_servicedorganisationvehiclejourney), 0);
begin
    insert into public.transmodel_servicedorganisationvehiclejourney (id,
                                                                      operating_on_working_days,
                                                                      serviced_organisation_id,
                                                                      vehicle_journey_id)
    select id,
           operating_on_working_days,
           serviced_organisation_id,
           vehicle_journey_id
    from bods.transmodel_servicedorganisationvehiclejourney ts
    where ts.id > max_current
    on conflict do nothing;
end;
$$;

alter procedure update_transmodel_servicedorganisationvehiclejourney owner to abods_proxy_rw;
