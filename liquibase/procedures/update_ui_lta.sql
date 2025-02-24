create or replace procedure update_ui_lta()
 LANGUAGE plpgsql
AS $procedure$
begin
    INSERT INTO public.ui_lta
    (id, "name")
    SELECT
        id,
        "name"
    from
        bods.ui_lta
    on conflict("name")
    DO UPDATE SET
        "name" = EXCLUDED."name";

    DELETE FROM public.ui_lta
    WHERE id NOT IN (SELECT id FROM bods.ui_lta);

end; $procedure$
;

alter procedure update_ui_lta owner to abods_rw;