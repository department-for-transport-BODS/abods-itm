DO $$
BEGIN
  IF EXISTS(SELECT *
    FROM information_schema.columns
    WHERE table_name='otc_inactiveservice'
    AND table_schema='bods'
    and column_name='registration_number')
  THEN
      ALTER FOREIGN table bods.otc_inactiveservice
      alter column registration_number
      type varchar(255);
  END IF;
END $$;