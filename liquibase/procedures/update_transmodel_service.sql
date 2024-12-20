create or replace procedure update_transmodel_service()
    language plpgsql
as
$$
declare
    max_current int := coalesce((select max(id)
                                 from public.transmodel_service), 0);
begin
    insert into public.transmodel_service (id,
                                           service_code,
                                           "name",
                                           other_names,
                                           start_date,
                                           end_date,
                                           revision_id,
                                           service_type,
                                           txcfileattributes_id)
    select id,
           service_code,
           "name",
           other_names,
           start_date,
           end_date,
           revision_id,
           service_type,
           txcfileattributes_id
    from bods.transmodel_service ts
    where ts.id > max_current
    on conflict do nothing;
end;
$$;
