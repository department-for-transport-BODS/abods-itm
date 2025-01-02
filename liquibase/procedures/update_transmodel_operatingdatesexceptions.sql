create or replace procedure update_transmodel_operatingdatesexceptions()
    language plpgsql
as
$$
declare
    max_current int := coalesce((select max(id)
                                 from public.transmodel_operatingdatesexceptions), 0);
begin
    insert into public.transmodel_operatingdatesexceptions (id,
                                                            operating_date,
                                                            vehicle_journey_id)
    select id,
           operating_date,
           vehicle_journey_id
    from bods.transmodel_operatingdatesexceptions too
    where too.id > max_current
    on conflict do nothing;
end;
$$;

alter procedure update_transmodel_operatingdatesexceptions owner to abods_proxy_rw;
