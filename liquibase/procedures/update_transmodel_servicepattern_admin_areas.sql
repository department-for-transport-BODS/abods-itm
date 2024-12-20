create or replace procedure update_transmodel_servicepattern_admin_areas()
    language plpgsql
as
$$
declare
    max_current int := coalesce((select max(id)
                                 from public.transmodel_servicepattern_admin_areas), 0);
begin
    insert into public.transmodel_servicepattern_admin_areas (id,
                                                              servicepattern_id,
                                                              adminarea_id)
    select id,
           servicepattern_id,
           adminarea_id
    from bods.transmodel_servicepattern_admin_areas tsaa
    where tsaa.id > max_current
    on conflict do nothing;
end;
$$;
