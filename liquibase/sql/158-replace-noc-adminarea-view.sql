CREATE TABLE IF NOT EXISTS public.noc_adminarea_import (
    national_operator_code text NOT NULL,
    adminarea_id int4 NOT NULL
);

ALTER TABLE IF EXISTS public.noc_adminarea_import
    OWNER TO abods_rw;

INSERT INTO public.noc_adminarea_import (
national_operator_code, adminarea_id
)
SELECT national_operator_code, adminarea_id
FROM public.noc_adminarea;

DROP VIEW IF EXISTS public.bods_organisationoperator;

DROP MATERIALIZED VIEW IF EXISTS public.noc_adminarea;

CREATE OR REPLACE VIEW public.noc_adminarea
AS SELECT national_operator_code, adminarea_id
FROM public.noc_adminarea_import;

ALTER VIEW IF EXISTS public.noc_adminarea OWNER TO abods_rw;

CREATE OR REPLACE VIEW public.bods_organisationoperator
AS SELECT oo.organisation_id,
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
 SELECT bo.id AS organisation_id,
    na.national_operator_code AS operatorref
   FROM bods_organisation bo
     RIGHT JOIN bods.organisation_organisation_admin_areas ooaa ON bo.id = ooaa.organisation_id
     LEFT JOIN noc_adminarea na ON na.adminarea_id = ooaa.adminarea_id
  GROUP BY bo.id, na.national_operator_code;

ALTER VIEW IF EXISTS public.bods_organisationoperator OWNER TO abods_rw;