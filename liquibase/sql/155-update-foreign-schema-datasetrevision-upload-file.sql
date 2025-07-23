DO $$
BEGIN
  IF EXISTS(SELECT *
    FROM information_schema.columns
    WHERE table_name='organisation_datasetrevision'
    AND table_schema='bods'
    and column_name='upload_file')
  THEN
      ALTER FOREIGN table bods.organisation_datasetrevision
      alter column upload_file
      type varchar(256);
  END IF;
END $$;
