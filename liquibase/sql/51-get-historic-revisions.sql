-- DROP FUNCTION public.get_historic_revisions_v4(date);

CREATE OR REPLACE FUNCTION public.get_historic_revisions_v4(partition_date date)
    RETURNS TABLE(revision_id bigint, dataset_id integer)
    LANGUAGE plpgsql
    AS $function$
        begin
            RETURN QUERY
            WITH datelist AS (
                SELECT generate_series(partition_date, partition_date, '1 day') AS query_date
            ),
            potential_datasets AS (
                SELECT od2.id dataset_table_id, od2.dataset_type
                FROM organisation_dataset od2
                WHERE od2.dataset_type = 1
            ),
            potential_revisions AS (
                SELECT dl.query_date, od.*, pd.*
                FROM datelist dl
                CROSS JOIN organisation_datasetrevision od
                INNER JOIN potential_datasets pd ON pd.dataset_table_id = od.dataset_id
                WHERE od.published_at <= dl.query_date
                AND od.status IN ('live', 'inactive', 'expired')
            ),
            inactive_at_date_prequery AS (
                SELECT *, rank() OVER (PARTITION BY pr.dataset_id ORDER BY pr.id DESC) AS id_rank
                FROM potential_revisions pr
            ),
            inactive_at_date AS (
                SELECT DISTINCT i.dataset_id
                FROM inactive_at_date_prequery i
                WHERE id_rank = 1
                AND modified < query_date
                AND status IN ('inactive', 'expired')
            ),
            ranked_revisions AS (
                SELECT pr.*, rank() OVER (PARTITION BY pr.dataset_id ORDER BY pr.id DESC) AS id_rank
                FROM potential_revisions pr
                LEFT JOIN inactive_at_date iad ON pr.dataset_id = iad.dataset_id
                WHERE iad.dataset_id IS NULL
            ), -- rank revisions which are not inactive at date by most modified
            highest_revisions as (
                select rr.*
                from ranked_revisions rr
                where rr.id_rank = 1
            )

            select distinct r.id as revision_id, r.dataset_id as dataset_id from highest_revisions r;
        end; 
    $function$
;