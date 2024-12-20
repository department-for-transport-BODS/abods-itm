create or replace procedure update_transmodel_operatingprofile()
    language plpgsql
as
$$
declare
    max_current int := coalesce((select max(id)
                                 from public.transmodel_operatingprofile), 0);
begin
    insert into public.transmodel_operatingprofile (id,
                                                    day_of_week,
                                                    vehicle_journey_id)
    select id,
           day_of_week,
           vehicle_journey_id
    from bods.transmodel_operatingprofile too
    where too.id > max_current
    on conflict do nothing;
end;
$$;
