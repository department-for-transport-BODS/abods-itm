create or replace procedure generate_expected_tables(IN partition_date date)
    language plpgsql
as
$$
begin
    RAISE NOTICE '% Deleting expected journeys for %', clock_timestamp(), partition_date::text;

    delete from expected_journeys where date_of_journey = partition_date;

    RAISE NOTICE '% Inserting expected journeys for %', clock_timestamp(), partition_date::text;

    insert into expected_journeys (date_of_journey,
                                   operator_noc,
                                   line_name,
                                   noc_and_line_and_servicecode,
                                   journey_code,
                                   group_id,
                                   stop_count,
                                   expected_journey_start,
                                   journey_pattern_description,
                                   vehicle_journey_id,
                                   day_of_week,
                                   admin_area_id,
                                   expected_journey_end,
                                   direction)
    with journeys as (select distinct t.date_of_journey,
                                      t.operator_noc,
                                      t.line_name,
                                      concat(t.operator_noc, '-', t.line_name, '-', t.service_code) as noc_and_line_and_servicecode,
                                      t.journey_code,
                                      t.group_id,
                                      count(stop_index) over w                                      as stop_count,
                                      first_value(t.expected_departure_time) over w                 as start_time,
                                      ts.description                                                as journey_pattern_description,
                                      t.vehiclejourney_id,
                                      t.day_of_week,
                                      t.admin_area_id,
                                      last_value(t.expected_departure_time) over w                  as end_time,
                                      t.direction
                      from "Timetable" t
                               left join transmodel_servicepattern ts
                                         on t.servicepattern_id = ts.id
                      where t.date_of_journey = partition_date
                      and (t.registered is null or t.registered = true)
                      window w as (
                              partition by t.group_id, t.vehiclejourney_id
                              order by t.stop_index asc
                              range between unbounded preceding and unbounded following
                              ))
    select date_of_journey,
           operator_noc,
           line_name,
           noc_and_line_and_servicecode,
           journey_code,
           group_id,
           stop_count,
           start_time,
           journey_pattern_description,
           vehiclejourney_id,
           day_of_week,
           array_agg(admin_area_id) as admin_area_id,
           end_time,
           direction
    from journeys
    group by date_of_journey,
             operator_noc,
             line_name,
             noc_and_line_and_servicecode,
             journey_code,
             group_id,
             stop_count,
             start_time,
             journey_pattern_description,
             vehiclejourney_id,
             day_of_week,
             end_time,
             direction;

    RAISE NOTICE '% Analysing expected journeys for %', clock_timestamp(), partition_date::text;

    analyse expected_journeys;

    RAISE NOTICE '% Deleting expected_services_by_date for %', clock_timestamp(), partition_date::text;

    delete from expected_services_by_date where date_of_journey = partition_date;

    RAISE NOTICE '% Inserting expected_services_by_date for %', clock_timestamp(), partition_date::text;

    insert into expected_services_by_date (date_of_journey,
                                           noc_and_line_and_servicecode,
                                           admin_area_id)
    select date_of_journey,
           noc_and_line_and_servicecode,
           array_agg(admin_area_id) as admin_area_id
    from (select distinct date_of_journey,
                          noc_and_line_and_servicecode,
                          unnest(admin_area_id) as admin_area_id
          from expected_journeys
          where date_of_journey = partition_date)
    group by date_of_journey,
             noc_and_line_and_servicecode;

    RAISE NOTICE '% Analysing expected_services_by_date for %', clock_timestamp(), partition_date::text;

    analyse expected_services_by_date;

    RAISE NOTICE '% Upserting service_details for %', clock_timestamp(), partition_date::text;

	WITH journey_data AS (
	    SELECT
	        ej.noc_and_line_and_servicecode,
	        ej.operator_noc,
	        split_part(split_part(ej.noc_and_line_and_servicecode, '-', 3), ':', 1) AS license,
	        ej.line_name,
	        FIRST_VALUE(ej.journey_pattern_description)
	            OVER (PARTITION BY ej.noc_and_line_and_servicecode ORDER BY ej.stop_count DESC, ej.journey_pattern_description ASC) AS service_name,
	        ej.admin_area_id
	    FROM expected_journeys ej
	    WHERE ej.date_of_journey = partition_date
	)
	
	INSERT INTO service_details (
	    noc_and_line_and_servicecode,
	    operator_noc,
	    license,
	    line_name,
	    service_name,
	    admin_areas
	)
	SELECT
	    jd.noc_and_line_and_servicecode,
	    jd.operator_noc,
	    jd.license,
	    jd.line_name,
	    jd.service_name,
	    ARRAY_AGG(DISTINCT ua.admin_area_id) AS admin_areas
	FROM journey_data jd,
	     LATERAL unnest(jd.admin_area_id) AS ua(admin_area_id)
	GROUP BY
	    jd.noc_and_line_and_servicecode,
	    jd.operator_noc,
	    jd.license,
	    jd.line_name,
	    jd.service_name
	
	ON CONFLICT (noc_and_line_and_servicecode)
	DO UPDATE SET
	    operator_noc = EXCLUDED.operator_noc,
	    line_name = EXCLUDED.line_name,
	    service_name = EXCLUDED.service_name,
	    license = EXCLUDED.license,
	    admin_areas = (
	        SELECT ARRAY(
	            SELECT DISTINCT unnest(service_details.admin_areas || EXCLUDED.admin_areas)
	        )
	    );

    RAISE NOTICE '% Analysing service_details for %', clock_timestamp(), partition_date::text;

    analyse service_details;

    RAISE NOTICE '% Refreshing expected_services for %', clock_timestamp(), partition_date::text;

    refresh materialized view expected_services;

    RAISE NOTICE '% Deleting expected operators for %', clock_timestamp(), partition_date::text;

    delete from expected_operators where date_of_journey = partition_date;

    RAISE NOTICE '% Inserting expected operators for %', clock_timestamp(), partition_date::text;

    insert into expected_operators (date_of_journey,
                                    operator_noc,
                                    operator_name)
    select distinct es.date_of_journey, es.operator_noc, o."name"
    from expected_services es
             left join traveline_operators o on
        o.noc_code = es.operator_noc
    where es.date_of_journey = partition_date;

    RAISE NOTICE '% Analysing expected operators for %', clock_timestamp(), partition_date::text;

    analyse expected_operators;

    RAISE NOTICE '% generate_expected_tables complete', clock_timestamp();

end;
$$;

alter procedure generate_expected_tables owner to abods_proxy_rw;
