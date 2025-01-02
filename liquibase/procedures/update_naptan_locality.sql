create or replace procedure update_naptan_locality()
    language plpgsql
as
$$
begin
    insert into public.naptan_locality (gazetteer_id,
                                        "name",
                                        easting,
                                        northing,
                                        admin_area_id,
                                        district_id)
    select gazetteer_id,
           "name",
           easting,
           northing,
           admin_area_id,
           district_id
    from bods.naptan_locality nl
    on conflict (gazetteer_id)
        do update set ("name", easting, northing, admin_area_id, district_id) = (EXCLUDED."name", EXCLUDED.easting,
                                                                                 EXCLUDED.northing,
                                                                                 EXCLUDED.admin_area_id,
                                                                                 EXCLUDED.district_id);
end;
$$;

alter procedure update_naptan_locality owner to abods_proxy_rw;
