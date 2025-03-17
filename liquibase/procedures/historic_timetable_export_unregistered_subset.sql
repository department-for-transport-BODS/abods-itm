create or replace procedure historic_timetable_export_unregistered_subset(IN partition_date date)
    language plpgsql
as
$$
DECLARE
    datestring TEXT := to_char(partition_date, 'YYYY-MM-DD');
BEGIN
    RAISE NOTICE '% Exporting timetable_unregistered_subset for date %', clock_timestamp(), partition_date::TEXT;

    PERFORM (SELECT COUNT(*)
             FROM aws_s3.query_export_to_s3(
                     format('
                        SELECT group_id,
                               stop_index,
                               stop_latitude,
                               stop_longitude,
                               expected_departure_time::TIME AS expected_departure_time,
                               timetable_id,
                               date_of_journey,
                               direction,
                               operator_noc
                        FROM public."Timetable"
                        WHERE date_of_journey = ''%s''::DATE
						and reprocessing_required = True
                        ORDER BY group_id ASC,
                                 direction ASC,
                                 stop_index ASC
                            ', datestring),
                     aws_commons.create_s3_uri(
                             concat('abods-', SPLIT_PART(aurora_db_instance_identifier(), '-', 2), '-exporter-bucket'),
                             concat(
                                     'historic/csv/timetable/YYYY=',
                                     DATE_PART('year', partition_date),
                                     '/MM=',
                                     LPAD(DATE_PART('month', partition_date)::TEXT, 2, '0'),
                                     '/',
                                     datestring,
                                     '.csv'
                             ),
                             'eu-west-2'
                     ),
                     options := 'format csv'
                  ));

    RAISE NOTICE '% Exported timetable for date %', clock_timestamp(), partition_date::TEXT;
END;
$$;

alter procedure historic_timetable_export_unregistered_subset owner to abods_proxy_rw;
