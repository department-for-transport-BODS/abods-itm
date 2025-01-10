create or replace procedure get_date_range(IN period_type character varying, OUT start_date date, OUT end_date date)
    language plpgsql
as
$$
BEGIN
    end_date := CURRENT_DATE - INTERVAL '1 day';

    IF period_type = 'last_7_days' THEN
        start_date := end_date - INTERVAL '6 days';
        RAISE NOTICE 'last_7_days';

    ELSEIF period_type = 'last_28_days' THEN
        start_date := end_date - INTERVAL '27 days';
        RAISE NOTICE 'last_28_days';

    ELSEIF period_type = 'month_to_date' THEN
        start_date := DATE_TRUNC('month', end_date);
        RAISE NOTICE 'month_to_date';

    ELSEIF period_type = 'last_month' THEN
        start_date := DATE_TRUNC('month', end_date) - INTERVAL '1 month';
        end_date := DATE_TRUNC('month', end_date) - INTERVAL '1 day';
        RAISE NOTICE 'last_month';

    ELSE
        start_date := NULL;
        end_date := NULL;

    END IF;
END;
$$;

alter procedure get_date_range owner to abods_proxy_rw;
