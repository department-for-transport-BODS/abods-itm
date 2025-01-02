create or replace procedure update_naptan_adminarea()
    language plpgsql
as
$$
begin
    insert into public.naptan_adminarea (id,
                                         "name",
                                         traveline_region_id,
                                         atco_code,
                                         ui_lta_id)
    select id,
           "name",
           traveline_region_id,
           atco_code,
           ui_lta_id
    from bods.naptan_adminarea na
    on conflict (id)
        do update set ("name", traveline_region_id, atco_code, ui_lta_id) = (EXCLUDED."name",
                                                                             EXCLUDED.traveline_region_id,
                                                                             EXCLUDED.atco_code, EXCLUDED.ui_lta_id);
end;
$$;

alter procedure update_naptan_adminarea owner to abods_proxy_rw;
