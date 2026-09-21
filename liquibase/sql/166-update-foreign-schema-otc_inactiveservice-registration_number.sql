DO $$
  declare otc_inactiveservice_def text;
  declare exec_text text;
BEGIN
  IF EXISTS(SELECT * 
    FROM public.bods_otcinactiveservice
    WHERE table_name='bods_otcinactiveservice'
    AND table_schema='public')
  THEN
    otc_inactiveservice_def := pg_get_viewdef('public.bods_otcinactiveservice');
    drop view public.bods_otcinactiveservice;
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
    exec_text := format('create view public.bods_otcinactiveservice as %s', 
        otc_inactiveservice_def);
    execute exec_text;
  ELSE
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
  END IF;
END $$;