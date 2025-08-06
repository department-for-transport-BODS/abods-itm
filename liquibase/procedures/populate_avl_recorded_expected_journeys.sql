CREATE OR REPLACE PROCEDURE public.populate_avl_recorded_expected_journeys(
    IN partition_date date DEFAULT (CURRENT_DATE - '1 day'::interval)
)
LANGUAGE plpgsql
AS $procedure$
BEGIN
    RAISE NOTICE '% Start running populate_avl_recorded_expected_journeys ', clock_timestamp();

    -- Step 1: Set all to TRUE
    UPDATE public.expected_journeys
    SET avl_recorded = TRUE
    WHERE date_of_journey = partition_date;

    -- Step 2: Set relevant ones to FALSE
    UPDATE public.expected_journeys ej
    SET avl_recorded = FALSE
    WHERE EXISTS (
        SELECT 1
        FROM public."Timetable" t
        WHERE t.group_id = ej.group_id
          AND t.date_of_journey = partition_date
          AND t.incomplete_reason IN (1, 2, 3)
    )
    AND ej.date_of_journey = partition_date;

    RAISE NOTICE '% populate_avl_recorded_expected_journeys complete', clock_timestamp();
END;
$procedure$;


