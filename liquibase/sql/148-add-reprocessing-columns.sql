alter foreign table if exists bods.organisation_datasetrevision
ADD COLUMN modified_before_reprocessing TIMESTAMPTZ,
ADD COLUMN status_before_reprocessing TEXT;

ALTER TABLE organisation_datasetrevision
ADD COLUMN modified_before_reprocessing TIMESTAMPTZ,
ADD COLUMN status_before_reprocessing TEXT;
