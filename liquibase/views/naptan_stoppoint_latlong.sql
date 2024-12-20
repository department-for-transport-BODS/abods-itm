create or replace view naptan_stoppoint_latlong
            (id, atco_code, naptan_code, common_name, street, indicator, admin_area_id, locality_id, stop_areas,
             bus_stop_type, stop_type, longitude, latitude)
as
SELECT id,
       atco_code,
       naptan_code,
       common_name,
       street,
       indicator,
       admin_area_id,
       locality_id,
       stop_areas,
       bus_stop_type,
       stop_type,
       st_x(location) AS longitude,
       st_y(location) AS latitude
FROM naptan_stoppoint;
