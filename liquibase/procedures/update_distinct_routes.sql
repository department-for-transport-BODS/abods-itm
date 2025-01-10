create or replace procedure update_distinct_routes(IN partition_date date)
    language plpgsql
as
$$
begin

    RAISE NOTICE 'Updating distinct_routes for % at %', partition_date, clock_timestamp();

    RAISE NOTICE 'Creating temp_distinct_route_calcs for % at %', partition_date, clock_timestamp();

    drop table if exists temp_distinct_route_calc;
    create temporary table temp_distinct_route_calc as
    select distinct concat(operator_noc, '-', line_name, '-', service_code) as noc_and_line_and_servicecode,
                    string_agg(
                    atco_code,
                    ','
                              ) over (
                        partition by group_id
                        order by
                            expected_departure_time asc,
                            stop_index asc,
                            timetable_id asc
                        range between
                            unbounded preceding
                            and unbounded following
                        )                                                   as route
    from public."Timetable"
    where date_of_journey = partition_date;

    RAISE NOTICE 'Inserting new distinct routes from  temp_distinct_route_calc to distinct_routes for % at %', partition_date, clock_timestamp();

    insert into public.distinct_routes (route)
    select distinct route
    from temp_distinct_route_calc
    on conflict (route)
        do nothing;

    RAISE NOTICE 'Analysing distinct_routes at %' , current_timestamp;

    analyse public.distinct_routes;

    RAISE NOTICE 'Inserting new distinct routes / noc/line/servicecode matches from temp_distinct_route_calc to servicepattern_route for % at %', partition_date, clock_timestamp();

    insert into public.servicepattern_route (distinct_route_id,
                                             noc_and_line_and_servicecode)
    select distinct dr.id,
                    ter.noc_and_line_and_servicecode
    from temp_distinct_route_calc ter
             join public.distinct_routes dr
                  on dr.route = ter.route
    on conflict(
        distinct_route_id,
        noc_and_line_and_servicecode
        ) do nothing;

    RAISE NOTICE 'Done at %', clock_timestamp();

end;
$$;

alter procedure update_distinct_routes owner to abods_proxy_rw;
