ALTER TABLE public.transmodel_servicepatterndistance
DROP CONSTRAINT IF EXISTS fk_service_pattern;

alter foreign table if exists bods.transmodel_servicepatterndistance
ADD COLUMN coord_track_distance INT4;

ALTER TABLE transmodel_servicepatterndistance
ADD COLUMN coord_track_distance INT4;