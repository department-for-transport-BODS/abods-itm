create or replace procedure update_transmodel_vehiclejourney()
    language plpgsql
as
$$
declare
    max_current int := coalesce((select max(id)
                                 from public.transmodel_vehiclejourney), 0);
begin
    insert into public.transmodel_vehiclejourney (id,
                                                  start_time,
                                                  direction,
                                                  journey_code,
                                                  line_ref,
                                                  departure_day_shift,
                                                  service_pattern_id,
                                                  block_number)
    select id,
           start_time,
           direction,
           journey_code,
           line_ref,
           departure_day_shift,
           service_pattern_id,
           block_number
    from bods.transmodel_vehiclejourney tvj
    where tvj.id > max_current
    on conflict do nothing;
end;
$$;

alter procedure update_transmodel_vehiclejourney owner to abods_proxy_rw;
