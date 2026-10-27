DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'auto_test_ro') THEN
        EXECUTE 'GRANT SELECT ON TABLE
            public.bods_organisationoperator,
            public.bods_userorganisation,
            public.bods_user
        TO auto_test_ro';
    ELSE
        RAISE NOTICE 'Role auto_test_ro does not exist; skipping TEST-only grants';
    END IF;
END
$$;
