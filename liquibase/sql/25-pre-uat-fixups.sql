CREATE OR REPLACE VIEW public.bods_user
AS SELECT uu.id,
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
  GROUP BY uu.id, uu.username, uu.email, uu.first_name, uu.last_name, uu.password, uu.is_superuser, uu.is_active, uu.account_type
  ORDER BY uu.account_type, uu.id;

  GRANT SELECT ON public.bods_user TO abods_rw;