DO $$
BEGIN
  IF EXISTS(SELECT *
    FROM information_schema.columns
    WHERE table_name='transmodel_vehiclejourney'
    AND table_schema='bods'
    and column_name='block_number')
  THEN
      ALTER FOREIGN table bods.transmodel_vehiclejourney
      alter column block_number
      type varchar(20);
  END IF;
END $$;
