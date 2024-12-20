create or replace procedure update_organisation_dataset()
    language plpgsql
as
$$
declare
    max_current int := coalesce((select max(id)
                                 from public.organisation_dataset),
                                0);

begin
    insert
    into public.organisation_dataset (id,
                                      created,
                                      modified,
                                      live_revision_id,
                                      organisation_id,
                                      contact_id,
                                      dataset_type,
                                      avl_feed_status,
                                      avl_feed_last_checked,
                                      is_dummy)
    select id,
           created,
           modified,
           live_revision_id,
           organisation_id,
           contact_id,
           dataset_type,
           avl_feed_status,
           avl_feed_last_checked,
           is_dummy
    from bods.organisation_dataset od
    on conflict (id) do update set (
                                    created,
                                    modified,
                                    live_revision_id,
                                    organisation_id,
                                    contact_id,
                                    dataset_type,
                                    avl_feed_status,
                                    avl_feed_last_checked,
                                    is_dummy
                                       ) = (
                                            EXCLUDED.created,
                                            EXCLUDED.modified,
                                            EXCLUDED.live_revision_id,
                                            EXCLUDED.organisation_id,
                                            EXCLUDED.contact_id,
                                            EXCLUDED.dataset_type,
                                            EXCLUDED.avl_feed_status,
                                            EXCLUDED.avl_feed_last_checked,
                                            EXCLUDED.is_dummy
        );
end;

$$;
