create or replace procedure repopulate_distinct_routes(IN number_of_days INT)
    language plpgsql
as
$$

DECLARE
    i INT := 0;
    date_value DATE;
BEGIN

    DELETE from public.distinct_routes;

    RAISE NOTICE 'Rows deleted from distinct_routes_table at %', clock_timestamp();

    FOR i IN 0..(number_of_days - 1) LOOP
        date_value := CURRENT_DATE - i;
        CALL update_distinct_routes(date_value);
    END LOOP;

    RAISE NOTICE 'Done at %', clock_timestamp();
END;
$$;

alter procedure repopulate_distinct_routes owner to abods_proxy_rw;