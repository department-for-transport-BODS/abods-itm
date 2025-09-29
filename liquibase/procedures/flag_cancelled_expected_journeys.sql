create or replace procedure flag_cancelled_expected_journeys(IN partition_date date)
    language plpgsql
as
$$
begin
    -- Set all is_cancelled to FALSE for the partition date before flagging cancelled ones
    UPDATE expected_journeys 
    SET is_cancelled = FALSE 
    WHERE date_of_journey = partition_date;

    RAISE NOTICE '% Flagging cancelled journeys for %', clock_timestamp(), partition_date::text;

    UPDATE expected_journeys ej
    SET is_cancelled = TRUE
    FROM (
        SELECT DISTINCT ON (producer_ref, situation_number)
            producer_ref,
            operator_noc,
            line_name,
            journey_code,
            direction,
            date_of_journey
        FROM siri_sx_situations
        WHERE date_of_journey = partition_date
        ORDER BY producer_ref, situation_number, event_timestamp DESC
    ) latest_situation
    WHERE ej.date_of_journey = latest_situation.date_of_journey
    AND ej.operator_noc = latest_situation.operator_noc
    AND ej.line_name = latest_situation.line_name
    AND ej.journey_code = latest_situation.journey_code
    AND ej.direction = latest_situation.direction
    AND latest_situation.condition != 'normalService' -- # Cancelled service
    AND latest_situation.progress = 'open'; -- # On-going situation

    RAISE NOTICE '% flag_cancelled_expected_journeys complete', clock_timestamp();

end;
$$;

alter procedure flag_cancelled_expected_journeys owner to abods_proxy_rw;
