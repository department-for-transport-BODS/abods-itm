DO $$
  declare otc_inactiveservice_def text;
  declare exec_text text;
  declare view_exists boolean;
BEGIN
  -- 1. Check if the view exists and grab its definition first
  SELECT EXISTS (    -- Sets a true/false flag
    SELECT 1 
    FROM information_schema.views
    WHERE table_name = 'bods_otcinactiveservice'
      AND table_schema = 'public'
  ) INTO view_exists;

  IF view_exists THEN
    otc_inactiveservice_def := pg_get_viewdef('public.bods_otcinactiveservice');
    -- Drop it immediately to unlock the underlying foreign table columns
    DROP VIEW public.bods_otcinactiveservice;
  END IF;

  -- 2. Safe to alter the column now that the view's lock is gone
  IF EXISTS (
    SELECT 1 
    FROM information_schema.columns
    WHERE table_name = 'otc_inactiveservice'
      AND table_schema = 'bods'
      AND column_name = 'registration_number'
  ) THEN
    ALTER FOREIGN TABLE bods.otc_inactiveservice 
      ALTER COLUMN registration_number TYPE varchar(255);
  END IF;

  -- 3. Re-create the view if it existed originally
  IF view_exists THEN
    exec_text := format('create view public.bods_otcinactiveservice as %s', 
    otc_inactiveservice_def);
    execute exec_text;
  END IF;
END $$;