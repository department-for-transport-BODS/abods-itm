CREATE OR REPLACE PROCEDURE public.historic_timetable_export(IN partition_date DATE)
    LANGUAGE PLPGSQL AS
$procedure$
DECLARE
    datestring TEXT := to_char(partition_date, 'YYYY-MM-DD');
BEGIN
    RAISE NOTICE 'Exporting timetable for date %', partition_date::TEXT;

    SELECT *
    FROM aws_s3.query_export_to_s3(
            format('SELECT group_id,
                           row_number() OVER (PARTITION BY group_id
                                              ORDER BY group_id, expected_departure_time ASC, stop_index ASC) AS stop_index,
                           stop_latitude,
                           stop_longitude,
                           expected_departure_time::TIME AS expected_departure_time,
                           timetable_id,
                           date_of_journey,
                           direction,
                           operator_noc
                    FROM public."Timetable"
                    WHERE date_of_journey = ''%s''::DATE
                    ORDER BY group_id ASC,
                             expected_departure_time ASC,
                             stop_index ASC', datestring),
            aws_commons.create_s3_uri(
                    concat('abods-', SPLIT_PART(aurora_db_instance_identifier(), '-', 2), '-exporter-bucket'),
                    concat(
                            'historic/csv/timetable/YYYY=',
                            DATE_PART('year', partition_date),
                            '/MM=',
                            DATE_PART('month', partition_date),
                            '/',
                            datestring,
                            '.csv'
                    ),
                    'eu-west-2'
            ),
            options := 'format csv'
         );

    RAISE NOTICE 'Exported timetable for date %', partition_date::TEXT;
END;
$procedure$;


CREATE OR REPLACE PROCEDURE public.historic_avl_export(IN partition_date DATE)
    LANGUAGE PLPGSQL AS
$procedure$
DECLARE
    datestring TEXT := to_char(partition_date, 'YYYY-MM-DD');
BEGIN
    RAISE NOTICE 'Exporting sirivmpositions for date %', partition_date::TEXT;

    SELECT *
    FROM aws_s3.query_export_to_s3(
            format('SELECT *
                    FROM public."SiriVMPositions"
                    WHERE date_of_journey = ''%s''::DATE', datestring),
            aws_commons.create_s3_uri(
                    concat('abods-', SPLIT_PART(aurora_db_instance_identifier(), '-', 2), '-exporter-bucket'),
                    concat(
                            'historic/csv/siri/YYYY=',
                            DATE_PART('year', partition_date),
                            '/MM=',
                            DATE_PART('month', partition_date),
                            '/siri_vm_',
                            datestring,
                            '.csv'
                    ),
                    'eu-west-2'),
            options := 'format csv'
         );

    RAISE NOTICE 'Exported sirivmpositions for date %', partition_date::TEXT;
END;
$procedure$;

CREATE OR REPLACE PROCEDURE public.historic_matching_summary_generation(IN partition_date DATE)
    LANGUAGE PLPGSQL AS
$procedure$
BEGIN
    CALL public.generate_expected_tables(partition_date);
    CALL public.create_timetable_threshold_summary(partition_date);
    CALL public.populate_headway(partition_date);
    CALL public.summary_by_stops(partition_date);
    CALL public.summary_by_services(partition_date);
    CALL public.summary_by_operators(partition_date);
END;
$procedure$;
