create or replace procedure update_transmodel_servicepattern()
    language plpgsql
as
$$
declare
    max_current int := coalesce((select max(id)
                                 from public.transmodel_servicepattern), 0);
begin
    insert into public.transmodel_servicepattern (id,
                                                  service_pattern_id,
                                                  origin,
                                                  destination,
                                                  description,
                                                  geom,
                                                  revision_id,
                                                  line_name)
    select id,
           service_pattern_id,
           origin,
           destination,
           description,
           geom,
           revision_id,
           line_name
    from bods.transmodel_servicepattern ts
    where ts.id > max_current
    on conflict do nothing;
end;
$$;
