--changeset abodsuser:4

-- Tables
ALTER TABLE IF EXISTS public."Alert" OWNER TO abods_rw;
ALTER TABLE IF EXISTS public."Tokens" OWNER TO abods_rw;
ALTER TABLE IF EXISTS public."FeatureFlag" OWNER TO abods_rw;
ALTER TABLE IF EXISTS public."ApiInfo" OWNER TO abods_rw;
ALTER TABLE IF EXISTS traveline_operators OWNER TO abods_rw;
ALTER TABLE IF EXISTS public."SiriVMPositions" OWNER TO abods_rw;
ALTER TABLE IF EXISTS public.staging_timetable_avl_positions OWNER TO abods_rw;
ALTER TABLE IF EXISTS public.batch OWNER TO abods_rw;
ALTER TABLE IF EXISTS public.sirivm_matching_batch OWNER TO abods_rw;
ALTER TABLE IF EXISTS public.naptan_locality OWNER TO abods_rw;
ALTER TABLE IF EXISTS public.naptan_stoppoint OWNER TO abods_rw;
ALTER TABLE IF EXISTS public.staging_avl_positions OWNER TO abods_rw;

-- Views
ALTER VIEW IF EXISTS public.all_operators OWNER TO abods_rw;
ALTER VIEW IF EXISTS public.bods_operators OWNER TO abods_rw;
ALTER VIEW IF EXISTS public.bods_operators OWNER TO abods_rw;
ALTER VIEW IF EXISTS public.bods_organisation OWNER TO abods_rw;
ALTER VIEW IF EXISTS public.bods_organisationoperator OWNER TO abods_rw;
ALTER VIEW IF EXISTS public.bods_userorganisation OWNER TO abods_rw;
ALTER VIEW IF EXISTS public.bods_user OWNER TO abods_rw;

-- Function
ALTER FUNCTION public.load_avl_tables OWNER TO abods_rw;

-- Procedures
ALTER PROCEDURE public.generate_timetable OWNER TO abods_rw;