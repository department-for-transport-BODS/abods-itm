create or replace procedure update_ui_lta()
    language plpgsql
as
$$
DECLARE
BEGIN
    DELETE FROM public.ui_lta;

    INSERT INTO public.ui_lta
    (id, "name")
    SELECT
        id,
        "name"
    from
        bods.ui_lta;
END;
$$;

alter procedure update_ui_lta owner to abods_proxy_rw;
