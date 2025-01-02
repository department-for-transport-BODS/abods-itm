create or replace view bods_organisation(id, name, is_abods_global_viewer) as
WITH all_orgs AS (SELECT oo.id,
                         oo.name,
                         oo.is_abods_global_viewer
                  FROM bods.organisation_organisation oo
                           LEFT JOIN bods.organisation_operatorcode oo2 ON oo.id = oo2.organisation_id
                  WHERE oo2.noc IS NOT NULL
                     OR oo.is_abods_global_viewer = true)
SELECT id,
       name,
       bool_or(is_abods_global_viewer) AS is_abods_global_viewer
FROM all_orgs
GROUP BY id, name;

alter view bods_organisation owner to abods_proxy_rw;
