create or replace view bods_userorganisation(user_id, organisation_id) as
SELECT uuo.user_id,
       uuo.organisation_id
FROM bods_organisation bo
         LEFT JOIN bods.users_user_organisations uuo ON bo.id = uuo.organisation_id
GROUP BY uuo.user_id, uuo.organisation_id;
