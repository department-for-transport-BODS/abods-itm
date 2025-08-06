CREATE OR REPLACE PROCEDURE public.populate_avl_recorded_expected_journeys(
    IN partition_date date DEFAULT (CURRENT_DATE - '1 day'::interval)
)
LANGUAGE plpgsql
AS $procedure$
BEGIN
    RAISE NOTICE '% Start running populate_avl_recorded_expected_journeys ', clock_timestamp();

    UPDATE public.expected_journeys ej
    SET avl_recorded = CASE
        WHEN EXISTS (
            SELECT 1
            FROM public."Timetable" t
            WHERE t.group_id = ej.group_id
              AND t.date_of_journey = partition_date
              AND t.incomplete_reason IN (1, 2, 3)
        ) THEN FALSE
        ELSE TRUE
    END
    WHERE ej.date_of_journey = partition_date;

    RAISE NOTICE '% populate_avl_recorded_expected_journeys complete', clock_timestamp();
END;
$procedure$;
