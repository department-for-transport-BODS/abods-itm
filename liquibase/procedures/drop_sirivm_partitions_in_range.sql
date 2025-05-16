CREATE OR REPLACE PROCEDURE public.drop_sirivm_partitions_in_range(IN p_start_date date, IN p_end_date date DEFAULT NULL::date)
 LANGUAGE plpgsql
AS $procedure$
DECLARE
    v_current_date DATE;
    v_six_months_ago DATE := CURRENT_DATE - INTERVAL '6 months'; BEGIN
    -- Validate entire range first
    IF p_start_date > v_six_months_ago OR 
       COALESCE(p_end_date, p_start_date) > v_six_months_ago THEN
        RAISE EXCEPTION 'Date range cannot include partitions newer than %', v_six_months_ago;
    END IF;
    
    -- Process each date in range
    FOR v_current_date IN 
        SELECT generate_series(
            p_start_date, 
            COALESCE(p_end_date, p_start_date),
            INTERVAL '1 day'
        )::DATE
    LOOP
        CALL drop_sirivm_partition_by_date(v_current_date);
    END LOOP;
END;
$procedure$
;
