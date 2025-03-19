create or replace procedure repopulate_distinct_routes(IN number_of_days INT)
    language plpgsql
as
$$
BEGIN
    TRUNCATE public.distinct_routes;

    RAISE NOTICE 'Rows deleted from distinct_routes_table at %', clock_timestamp();

    FOR i IN 0..(number_of_days - 1) LOOP
        CALL update_distinct_routes(CURRENT_DATE - i);
    END LOOP;

    RAISE NOTICE 'Done at %', clock_timestamp();
END;
$$;

alter procedure repopulate_distinct_routes owner to abods_proxy_rw;