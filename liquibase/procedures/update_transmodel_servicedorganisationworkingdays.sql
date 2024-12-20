create or replace procedure update_transmodel_servicedorganisationworkingdays()
    language plpgsql
as
$$
declare
    max_current int := coalesce((select max(id)
                                 from public.transmodel_servicedorganisationworkingdays), 0);
begin
    insert into public.transmodel_servicedorganisationworkingdays (id,
                                                                   start_date,
                                                                   end_date,
                                                                   serviced_organisation_vehicle_journey_id)
    select id,
           start_date,
           end_date,
           serviced_organisation_vehicle_journey_id
    from bods.transmodel_servicedorganisationworkingdays ts
    where ts.id > max_current
    on conflict do nothing;
end;
$$;
