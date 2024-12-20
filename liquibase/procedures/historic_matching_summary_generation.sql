create or replace procedure historic_matching_summary_generation(IN partition_date date)
    language plpgsql
as
$$
BEGIN
    RAISE NOTICE '----------------Calling generate_expected_tables----------------';
    CALL public.generate_expected_tables(partition_date);

    RAISE NOTICE '----------------Calling create_timetable_threshold_summary----------------';
    CALL public.create_timetable_threshold_summary(partition_date);

    RAISE NOTICE '----------------Calling populate_headway----------------';
    CALL public.populate_headway(partition_date);

    RAISE NOTICE '----------------Calling summary_by_stops----------------';
    CALL public.summary_by_stops(partition_date);

    RAISE NOTICE '----------------Calling summary_by_services----------------';
    CALL public.summary_by_services(partition_date);

    RAISE NOTICE '----------------Calling summary_by_operators----------------';
    CALL public.summary_by_operators(partition_date);
END;
$$;
