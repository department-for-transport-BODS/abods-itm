create or replace procedure update_transmodel_nonoperatingdatesexceptions()
    language plpgsql
as
$$
declare
    max_current int := coalesce((select max(id)
                                 from public.transmodel_nonoperatingdatesexceptions), 0);
begin
    insert into public.transmodel_nonoperatingdatesexceptions (id,
                                                               non_operating_date,
                                                               vehicle_journey_id)
    select id,
           non_operating_date,
           vehicle_journey_id
    from bods.transmodel_nonoperatingdatesexceptions tn
    where tn.id > max_current
    on conflict do nothing;
end;
$$;

alter procedure update_transmodel_nonoperatingdatesexceptions owner to abods_proxy_rw;
