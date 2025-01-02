create or replace procedure update_all_naptan_tables()
    language plpgsql
as
$$
begin
    raise notice 'Running update_naptan_adminarea at %', current_timestamp;
    call public.update_naptan_adminarea();
    raise notice 'Running update_naptan_locality at %', current_timestamp;
    call public.update_naptan_locality();
    raise notice 'Running update_naptan_stoppoint at %', current_timestamp;
    call public.update_naptan_stoppoint();
end;
$$;

alter procedure update_all_naptan_tables owner to abods_proxy_rw;
