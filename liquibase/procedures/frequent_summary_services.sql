create or replace procedure public.frequent_summary_services(IN current_date date DEFAULT (CURRENT_DATE - '1 day'::interval))
    language plpgsql
as
$$
DECLARE
    tablename TEXT;

BEGIN
    tablename := 'timetable_frequent_summary_services';

    RAISE NOTICE '% Adding new data to %', clock_timestamp(), tablename;

    EXECUTE format
            ('INSERT INTO public.%I(
                                operator_noc,
                                service_code,
                                noc_and_line_and_servicecode,
                                line_name,
                                date_of_journey,
                                departure_hour,
                                departure_hour_only,
                                day_of_week,
                                max_early,
                                max_late,
                                avg_time_difference,
                                expected_headway,
                                actual_headway,
                                excess_wait_Time,
                                estimated,
                                headway_stops_count)
            WITH Timetable_CTE AS
                        (SELECT sub.operator_noc,
                                sub.service_code,
                                sub.noc_and_line_and_servicecode,
                                sub.line_name,
                                sub.date_of_journey,
                                date_trunc(''hour'', sub.expected_departure_time::timestamptz) AS departure_hour,
                                (
                                    EXTRACT(HOUR
                                            FROM sub.expected_departure_time)::text || '':00:00'' || CASE
                                                                                                    WHEN RIGHT(sub.expected_departure_time::text, 6) ~ ''^[+-]''
                                                                                                        THEN RIGHT(sub.expected_departure_time::text, 6)
                                                                                                    ELSE ''+00'' END
                                )::timetz AS departure_hour_only,
                                sub.day_of_week,
                                sub.max_early,
                                sub.max_late,
                                COALESCE(AVG(sub.avg_time_difference / 60.0), 0.0)           AS avg_time_difference,
                                AVG(sub.expected_headway)                                    AS expected_headway,
                                AVG(sub.actual_headway) FILTER (
                                    WHERE sub.actual_headway IS NOT NULL)                    AS actual_headway,
                                AVG(sub.headway_time_difference) FILTER (
                                    WHERE sub.actual_headway IS NOT NULL)                    AS excess_wait_Time,
                                sub.estimated,
                                sub.stop_id,
                                count(sub.actual_headway)                                    AS headway_stops_count
                        FROM (SELECT ttb.operator_noc,
                                    ttb.service_code,
                                    es.noc_and_line_and_servicecode,
                                    ttb.line_name,
                                    ttb.date_of_journey,
                                    ttb.day_of_week,
                                    ttb.expected_departure_time,
                                    COALESCE(ttb.actual_departure_time, ttb.timestamp_after_estimate) AS actual_departure_time,
                                    ttb.time_difference,
                                    CASE
                                        WHEN otp_state = ''Early''
                                            AND time_difference >= -600 THEN 10
                                        WHEN otp_state = ''Early''
                                            AND time_difference < -600
                                            AND time_difference >= -1200 THEN 20
                                        WHEN otp_state = ''Early''
                                            AND time_difference < -1200
                                            AND time_difference >= -1800 THEN 30
                                        WHEN otp_state = ''Early''
                                            AND time_difference < -1800
                                            AND time_difference >= -2400 THEN 40
                                        WHEN otp_state = ''Early''
                                            AND time_difference < -2400
                                            AND time_difference >= -3000 THEN 50
                                        WHEN otp_state = ''Early''
                                            AND time_difference < -3000
                                            AND time_difference >= -3600 THEN 60
                                        WHEN otp_state = ''Early''
                                            AND time_difference < -3600 THEN 70
                                        ELSE 0 END                                         AS max_early,
                                    CASE
                                        WHEN otp_state = ''Late''
                                            AND time_difference <= 600 THEN 10
                                        WHEN otp_state = ''Late''
                                            AND time_difference > 600
                                            AND time_difference <= 1200 THEN 20
                                        WHEN otp_state = ''Late''
                                            AND time_difference > 1200
                                            AND time_difference <= 1800 THEN 30
                                        WHEN otp_state = ''Late''
                                            AND time_difference > 1800
                                            AND time_difference <= 2400 THEN 40
                                        WHEN otp_state = ''Late''
                                            AND time_difference > 2400
                                            AND time_difference <= 3000 THEN 50
                                        WHEN otp_state = ''Late''
                                            AND time_difference > 3000
                                            AND time_difference <= 3600 THEN 60
                                        WHEN otp_state = ''Late''
                                            AND time_difference > 3600 THEN 70
                                        ELSE 0 END                                         AS max_late,
                                    ttb.time_difference                                    AS avg_time_difference,
                                    ttb.expected_headway,
                                    ttb.actual_headway,
                                    ttb.headway_time_difference,
                                    (ttb.timestamp_after_estimate IS NOT NULL)             AS estimated,
                                    ttb.stop_id
                            FROM public."Timetable" ttb
                                        INNER JOIN public.expected_services es ON
                                    ttb.date_of_journey = es.date_of_journey
                                AND ttb.operator_noc = es.operator_noc
                                AND ttb.line_name = es.line_name
                                AND ttb.service_code = split_part(es.noc_and_line_and_servicecode, ''-'', -1)
                            WHERE ttb.date_of_journey = % L
                                AND ttb.previous_group_id IS NOT NULL) AS sub
                        WHERE date_of_journey = % L
                        GROUP BY operator_noc,
                                service_code,
                                noc_and_line_and_servicecode,
                                stop_id,
                                line_name,
                                date_of_journey,
                                departure_hour,
                                departure_hour_only,
                                day_of_week,
                                max_early,
                                max_late,
                                estimated),
                    Timetable_Agg AS
                        (SELECT operator_noc,
                                service_code,
                                noc_and_line_and_servicecode,
                                line_name,
                                date_of_journey,
                                departure_hour,
                                departure_hour_only,
                                day_of_week,
                                max_early,
                                max_late,
                                avg(avg_time_difference)                   AS avg_time_difference,
                                sum(expected_headway * headway_stops_count) AS expected_headway,
                                sum(actual_headway * headway_stops_count)   AS actual_headway,
                                sum(excess_wait_Time * headway_stops_count) AS excess_wait_Time,
                                sum(headway_stops_count)                    AS headway_stops_count,
                                estimated
                        FROM Timetable_CTE
                        GROUP BY operator_noc,
                                service_code,
                                noc_and_line_and_servicecode,
                                line_name,
                                date_of_journey,
                                departure_hour,
                                departure_hour_only,
                                day_of_week,
                                max_early,
                                max_late,
                                estimated)
            SELECT operator_noc,
                    service_code,
                    noc_and_line_and_servicecode,
                    line_name,
                    date_of_journey,
                    departure_hour,
                    departure_hour_only,
                    day_of_week,
                    max_early,
                    max_late,
                    avg_time_difference,
                    CASE 
                        WHEN headway_stops_count = 0 THEN 0
                        ELSE (expected_headway / (headway_stops_count * 60))
                    END AS expected_headway,
                    CASE 
                        WHEN headway_stops_count = 0 THEN 0
                        ELSE (actual_headway / (headway_stops_count * 60))
                    END AS actual_headway,
                    CASE 
                        WHEN headway_stops_count = 0 THEN 0
                        ELSE (excess_wait_Time / (headway_stops_count * 60))
                    END AS excess_wait_Time,
                    estimated,
                    headway_stops_count
            FROM Timetable_Agg;',
                tablename,
                current_date,
                current_date);

    RAISE NOTICE '% frequent_summary_services complete', clock_timestamp();
END;
$$;

alter procedure frequent_summary_services owner to abods_proxy_rw;
