CREATE OR REPLACE PROCEDURE public.update_transmodel_servicepatterndistance()
 LANGUAGE plpgsql
AS $procedure$
declare
    max_current int := coalesce((select max(service_pattern_id)
                                 from public.transmodel_servicepatterndistance), 0);
begin
    insert into public.transmodel_servicepatterndistance (distance,
                                                  geom,
                                                  service_pattern_id,
                                                  coord_track_distance)
    select ts.distance,
           ts.geom,
           ts.service_pattern_id,
           ts.coord_track_distance
    from bods.transmodel_servicepatterndistance ts
    where ts.service_pattern_id > max_current
    on conflict do nothing;
end;
$procedure$
;
