ALTER TABLE public.transmodel_servicepatternstop DROP COLUMN IF EXISTS auto_sequence_number;

ALTER TABLE public."Timetable" DROP COLUMN IF EXISTS recorded_at_time_utc;

CREATE INDEX IF NOT EXISTS public.organisation_dataset_id_idx ON organisation_dataset (id);

ALTER TABLE public.timetable_threshold_summary ALTER COLUMN estimated DROP DEFAULT;

ALTER TABLE public.timetable_summary_operator_t ALTER COLUMN operator_noc SET NOT NULL;
ALTER TABLE public.timetable_summary_operator_t ALTER COLUMN date_of_journey SET NOT NULL;
ALTER TABLE public.timetable_summary_operator_t ALTER COLUMN departure_hour SET NOT NULL;
ALTER TABLE public.timetable_summary_operator_t ALTER COLUMN departure_hour_only SET NOT NULL;
ALTER TABLE public.timetable_summary_operator_t ALTER COLUMN day_of_week SET NOT NULL;
ALTER TABLE public.timetable_summary_operator_t ALTER COLUMN is_timing_point SET NOT NULL;
ALTER TABLE public.timetable_summary_operator_t ALTER COLUMN max_early SET NOT NULL;
ALTER TABLE public.timetable_summary_operator_t ALTER COLUMN max_late SET NOT NULL;
ALTER TABLE public.timetable_summary_operator_t ALTER COLUMN avg_time_difference SET NOT NULL;
ALTER TABLE public.timetable_summary_operator_t ALTER COLUMN admin_areas SET NOT NULL;

ALTER TABLE public.timetable_summary_service_tz ALTER COLUMN estimated SET NOT NULL;

ALTER TABLE public.timetable_summary_stops_tz ALTER COLUMN estimated SET NOT NULL;
ALTER TABLE public.timetable_summary_stops_tz ALTER COLUMN line_name SET NOT NULL;

ALTER TABLE public.feed_monitor_summary DROP CONSTRAINT IF EXISTS feed_monitor_summary_pk;

ALTER TABLE public.naptan_stoppoint ALTER COLUMN id            TYPE integer; -- was bigint
ALTER TABLE public.naptan_stoppoint ALTER COLUMN atco_code DROP NOT NULL;
ALTER TABLE public.naptan_stoppoint ALTER COLUMN atco_code     TYPE varchar(255); -- was text
ALTER TABLE public.naptan_stoppoint ALTER COLUMN naptan_code   TYPE varchar(12); -- was text
ALTER TABLE public.naptan_stoppoint ALTER COLUMN common_name DROP NOT NULL;
ALTER TABLE public.naptan_stoppoint ALTER COLUMN common_name   TYPE varchar(255); -- was text
ALTER TABLE public.naptan_stoppoint ALTER COLUMN street        TYPE varchar(255); -- was text
ALTER TABLE public.naptan_stoppoint ALTER COLUMN indicator     TYPE varchar(255); -- was text
ALTER TABLE public.naptan_stoppoint ALTER COLUMN location DROP NOT NULL;
ALTER TABLE public.naptan_stoppoint ALTER COLUMN locality_id   TYPE varchar(8); -- was text
ALTER TABLE public.naptan_stoppoint ALTER COLUMN stop_areas DROP NOT NULL;
ALTER TABLE public.naptan_stoppoint ALTER COLUMN stop_areas    TYPE varchar(255)[]; -- was text[]
ALTER TABLE public.naptan_stoppoint ALTER COLUMN bus_stop_type TYPE varchar(255); -- was text
ALTER TABLE public.naptan_stoppoint ALTER COLUMN stop_type     TYPE varchar(255); -- was text

ALTER TABLE public.timetable_summary_operator ADD COLUMN estimated boolean;
ALTER TABLE public.timetable_summary_service ADD COLUMN estimated boolean;

CREATE OR REPLACE VIEW bods_organisationoperator(organisation_id, operatorref) AS
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
         RIGHT JOIN organisation_organisation_admin_areas ooaa ON bo.id = ooaa.organisation_id
         LEFT JOIN noc_adminarea na ON na.adminarea_id = ooaa.adminarea_id
GROUP BY bo.id, na.national_operator_code;

ALTER VIEW bods_organisationoperator OWNER TO abods_proxy_rw;
