CREATE OR REPLACE PROCEDURE public.update_transmodel_servicepatterndistance()
 LANGUAGE plpgsql
AS $procedure$
declare
    max_current int := coalesce((select max(service_pattern_id)
                                 from public.transmodel_servicepatterndistance), 0);
begin
    insert into public.transmodel_servicepatterndistance (distance,
                                                  geom,
                                                  service_pattern_id)
    select distance,
           geom,
           service_pattern_id
    from bods.transmodel_servicepattern ts
    where ts.id > max_current
    on conflict do nothing;
end;
$procedure$
;
