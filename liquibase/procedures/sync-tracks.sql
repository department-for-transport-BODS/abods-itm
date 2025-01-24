create or replace procedure public.sync_tracks()
 LANGUAGE plpgsql
AS $procedure$
begin
    MERGE INTO public.transmodel_tracks AS target
    USING bods.transmodel_tracks AS source
    ON (target.from_atco_code = source.from_atco_code AND target.to_atco_code = source.to_atco_code)
    WHEN MATCHED THEN
        UPDATE SET
            geometry = ST_AsGeoJSON(source.geometry),
            distance = source.distance
    WHEN NOT MATCHED THEN
        INSERT (id, from_atco_code, to_atco_code, geometry, distance)
        VALUES (source.id, source.from_atco_code, source.to_atco_code, ST_AsGeoJSON(source.geometry), source.distance)
    
    DELETE FROM public.transmodel_tracks
    WHERE id NOT IN (SELECT id FROM bods.transmodel_tracks);

end; $procedure$
;

alter procedure public.transmodel_tracks owner to abods_rw;