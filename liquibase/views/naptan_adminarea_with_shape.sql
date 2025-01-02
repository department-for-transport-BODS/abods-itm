create or replace view naptan_adminarea_with_shape(id, name, atco_code, st_asgeojson) as
SELECT na.id,
       na.name,
       na.atco_code,
       st_asgeojson(st_flipcoordinates(nas.shape)) AS st_asgeojson
FROM naptan_adminarea na
         JOIN naptan_adminarea_shape nas ON na.id = nas.admin_area_id;

alter view naptan_adminarea_with_shape owner to abods_proxy_rw;
