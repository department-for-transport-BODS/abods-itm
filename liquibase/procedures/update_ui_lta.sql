create or replace procedure update_ui_lta()
 LANGUAGE plpgsql
AS $procedure$
begin
    DELETE FROM public.ui_lta;

    INSERT INTO public.ui_lta
    (id, "name")
    SELECT
        id,
        "name"
    from
        bods.ui_lta;

end; $procedure$
;

alter procedure update_ui_lta owner to abods_rw;
