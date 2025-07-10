ALTER TABLE service_details ADD COLUMN IF NOT EXISTS license TEXT;

DROP MATERIALIZED VIEW IF EXISTS public.expected_services;

CREATE MATERIALIZED VIEW public.expected_services
TABLESPACE pg_default
AS
SELECT DISTINCT 
    esbd.date_of_journey,
    sd.noc_and_line_and_servicecode,
    sd.operator_noc,
    esbd.license,
    sd.line_name,
    sd.service_name,
    esbd.admin_area_id,
    esbd.total_distance,
    esbd.avl_true_distance
FROM 
    expected_services_by_date esbd
LEFT JOIN 
    service_details sd 
    ON esbd.noc_and_line_and_servicecode = sd.noc_and_line_and_servicecode
WITH DATA;
