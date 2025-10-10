create or replace procedure update_naptan_adminarea_shape()
    language plpgsql
as
$$
begin
    delete from public.naptan_adminarea_shape;
    insert into public.naptan_adminarea_shape (admin_area_id, shape)
    select admin_area_id, st_concavehull(st_collect(location), 0.3)
    from public.naptan_stoppoint naa
    where st_intersects((select st_concavehull(st_collect(boundary), 0.9) from public.uk_borders), location)
    and admin_area_id not in (110, 147)
    group by admin_area_id;
end;
$$;

alter procedure update_naptan_adminarea_shape owner to abods_proxy_rw;
