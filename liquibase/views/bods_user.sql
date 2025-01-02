create or replace view bods_user
            (id, username, email, first_name, last_name, password, is_superuser, is_active, account_type, admin_org) as
SELECT uu.id,
       uu.username,
       uu.email,
       uu.first_name,
       uu.last_name,
       uu.password,
       uu.is_superuser,
       uu.is_active,
       uu.account_type,
       max(
               CASE
                   WHEN uu.account_type = 2 THEN bu.organisation_id
                   ELSE NULL::integer
                   END) AS admin_org
FROM bods_userorganisation bu
         LEFT JOIN bods.users_user uu ON bu.user_id = uu.id
GROUP BY uu.id, uu.username, uu.email, uu.first_name, uu.last_name, uu.password, uu.is_superuser, uu.is_active,
         uu.account_type
ORDER BY uu.account_type, uu.id;

alter view bods_user owner to abods_proxy_rw;
