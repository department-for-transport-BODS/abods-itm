create or replace procedure update_transmodel_service_service_patterns()
    language plpgsql
as
$$
declare
    max_current int := coalesce((select max(id)
                                 from public.transmodel_service_service_patterns), 0);
begin
    insert into public.transmodel_service_service_patterns (id,
                                                            service_id,
                                                            servicepattern_id)
    select id,
           service_id,
           servicepattern_id
    from bods.transmodel_service_service_patterns ts
    where ts.id > max_current
    on conflict do nothing;
end;
$$;
