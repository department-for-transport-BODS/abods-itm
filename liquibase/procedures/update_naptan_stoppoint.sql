create or replace procedure update_naptan_stoppoint()
    language plpgsql
as
$$
begin
    insert into public.naptan_stoppoint (id,
                                         atco_code,
                                         naptan_code,
                                         common_name,
                                         street,
                                         "indicator",
                                         "location",
                                         admin_area_id,
                                         locality_id,
                                         stop_areas,
                                         bus_stop_type,
                                         stop_type)
    select id,
           atco_code,
           naptan_code,
           common_name,
           street,
           "indicator",
           "location",
           admin_area_id,
           locality_id,
           stop_areas,
           bus_stop_type,
           stop_type
    from bods.naptan_stoppoint ns
    on conflict (id)
        do update set (
                       atco_code,
                       naptan_code,
                       common_name,
                       street,
                       "indicator",
                       "location",
                       admin_area_id,
                       locality_id,
                       stop_areas,
                       bus_stop_type,
                       stop_type
                          ) = (
                               EXCLUDED.atco_code,
                               EXCLUDED.naptan_code,
                               EXCLUDED.common_name,
                               EXCLUDED.street,
                               EXCLUDED."indicator",
                               EXCLUDED."location",
                               EXCLUDED.admin_area_id,
                               EXCLUDED.locality_id,
                               EXCLUDED.stop_areas,
                               EXCLUDED.bus_stop_type,
                               EXCLUDED.stop_type
        );
end;
$$;

alter procedure update_naptan_stoppoint owner to abods_proxy_rw;
