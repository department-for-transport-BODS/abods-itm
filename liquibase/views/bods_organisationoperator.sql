create or replace view bods_organisationoperator(organisation_id, operatorref) as
SELECT oo.organisation_id,
       oo.noc AS operatorref
FROM bods_organisation bo
         LEFT JOIN bods.organisation_operatorcode oo ON bo.id = oo.organisation_id
GROUP BY oo.organisation_id, oo.noc
UNION
SELECT bo.id AS organisation_id,
       ao.operatorref
FROM bods_organisation bo
         CROSS JOIN all_operators ao
WHERE bo.is_abods_global_viewer = true
GROUP BY bo.id, ao.operatorref
UNION
SELECT bo.id                     AS organisation_id,
       na.national_operator_code AS operatorref
FROM bods_organisation bo
         RIGHT JOIN bods.organisation_organisation_admin_areas ooaa ON bo.id = ooaa.organisation_id
         LEFT JOIN noc_adminarea na ON na.adminarea_id = ooaa.adminarea_id
GROUP BY bo.id, na.national_operator_code;

alter view bods_organisationoperator owner to abods_proxy_rw;
