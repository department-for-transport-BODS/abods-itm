create or replace procedure update_transmodel_tracks()
 LANGUAGE plpgsql
AS $procedure$
begin
    INSERT into public.transmodel_tracks(
        id, 
        from_atco_code, 
        to_atco_code, 
        geometry, 
        distance
    )
    SELECT
        id,
        from_atco_code, 
        to_atco_code, 
        ST_AsGeoJSON(geometry) as geometry, 
        distance
    from 
        bods.transmodel_tracks
    on conflict(id)
    DO UPDATE SET
        geometry = ST_AsGeoJSON(EXCLUDED.geometry),
        distance = EXCLUDED.distance;

    DELETE FROM public.transmodel_tracks
    WHERE id NOT IN (SELECT id FROM bods.transmodel_tracks);

end; $procedure$
;

alter procedure update_transmodel_tracks owner to abods_rw;
