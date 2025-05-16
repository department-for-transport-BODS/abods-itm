CREATE OR REPLACE PROCEDURE public.drop_sirivm_partition_by_date(IN p_date date default CURRENT_DATE - INTERVAL '6 months')
 LANGUAGE plpgsql
AS $$ DECLARE
    v_partition_name TEXT := format('SiriVMPositions_p%s', TO_CHAR(p_date, 'YYYY_MM_DD'));
    v_six_months_ago DATE := CURRENT_DATE - INTERVAL '6 months'; BEGIN
    -- 1. Strict date validation
    IF p_date > v_six_months_ago THEN
        RAISE EXCEPTION 'Cannot drop partition newer than 6 months ago (%)', v_six_months_ago;
    END IF;

    -- 2. Attempt to drop partition
    RAISE NOTICE 'Attempting to drop partition: %', v_partition_name;
    EXECUTE format('DROP TABLE %I', v_partition_name);
    
    RAISE NOTICE '%: Successfully dropped partition: %', clock_timestamp(), v_partition_name; EXCEPTION 
    WHEN UNDEFINED_TABLE THEN
        RAISE NOTICE '%: Partition % does not exist (skipping)', clock_timestamp(), v_partition_name;
    WHEN OTHERS THEN
        RAISE EXCEPTION '%: Failed to drop partition %: %', clock_timestamp(), v_partition_name, SQLERRM; END; $$
;
