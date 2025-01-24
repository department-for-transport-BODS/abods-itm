create or replace procedure public.sync_tracks()
 LANGUAGE plpgsql
AS $procedure$
begin
    MERGE INTO public.transmodel_tracks AS target
    USING bods.transmodel_tracks AS source
    ON (target.from_atco_code = source.from_atco_code AND target.to_atco_code = source.to_atco_code)
    WHEN MATCHED THEN
        UPDATE SET
            target.geometry = ST_AsGeoJSON(source.geometry),
            target.distance = source.distance
    WHEN NOT MATCHED BY TARGET THEN
        INSERT (id, from_atco_code, to_atco_code, geometry, distance)
        VALUES (source.id, source.from_atco_code, source.to_atco_code, ST_AsGeoJSON(source.geometry), source.distance)
    WHEN NOT MATCHED BY SOURCE THEN
        DELETE;

end; $procedure$
;

alter procedure public.transmodel_tracks owner to abods_rw;