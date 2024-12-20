create or replace view bods_organisation_organisation_admin_areas(id, organisation_id, adminarea_id) as
SELECT id,
       organisation_id,
       adminarea_id
FROM bods.organisation_organisation_admin_areas;
