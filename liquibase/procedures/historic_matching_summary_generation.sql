create or replace procedure historic_matching_summary_generation(IN partition_date date)
    language plpgsql
as
$$
BEGIN
    IF NOT EXISTS (SELECT 1
                   FROM public."Timetable"
                   WHERE date_of_journey = partition_date) THEN
        RAISE NOTICE 'No timetable data for date %', partition_date;
    ELSE
        RAISE NOTICE '% ----------------Calling generate_expected_tables----------------', clock_timestamp();
        CALL public.generate_expected_tables(partition_date);

        RAISE NOTICE '% ----------------Calling create_timetable_threshold_summary----------------', clock_timestamp();
        CALL public.create_timetable_threshold_summary(partition_date);

        RAISE NOTICE '% ----------------Calling populate_headway----------------', clock_timestamp();
        CALL public.populate_headway(partition_date);

        RAISE NOTICE '% ----------------Calling summary_by_stops----------------', clock_timestamp();
        CALL public.summary_by_stops(partition_date);

        RAISE NOTICE '% ----------------Calling summary_by_services----------------', clock_timestamp();
        CALL public.summary_by_services(partition_date);

        RAISE NOTICE '% ----------------Calling summary_by_operators----------------', clock_timestamp();
        CALL public.summary_by_operators(partition_date);
    END IF;

    RAISE NOTICE '% historic_matching_summary_generation complete', clock_timestamp();
END;
$$;

alter procedure historic_matching_summary_generation owner to abods_proxy_rw;
