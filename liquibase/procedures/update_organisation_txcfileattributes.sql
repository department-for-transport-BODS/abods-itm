create or replace procedure update_organisation_txcfileattributes()
    language plpgsql
as
$$
declare
    max_current int := coalesce((select max(id)
                                 from public.organisation_txcfileattributes), 0);
begin
    insert into public.organisation_txcfileattributes (id,
                                                       schema_version,
                                                       revision_number,
                                                       creation_datetime,
                                                       modification_datetime,
                                                       filename,
                                                       service_code,
                                                       revision_id,
                                                       modification,
                                                       national_operator_code,
                                                       licence_number,
                                                       operating_period_end_date,
                                                       operating_period_start_date,
                                                       public_use,
                                                       line_names,
                                                       destination,
                                                       origin,
                                                       hash)
    select id,
           schema_version,
           revision_number,
           creation_datetime,
           modification_datetime,
           filename,
           service_code,
           revision_id,
           modification,
           national_operator_code,
           licence_number,
           operating_period_end_date,
           operating_period_start_date,
           public_use,
           line_names,
           destination,
           origin,
           hash
    from bods.organisation_txcfileattributes ot
    where ot.id > max_current
    on conflict do nothing;
end;
$$;
