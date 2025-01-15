create or replace procedure historic_avl_export(IN partition_date date)
    language plpgsql
as
$$
DECLARE
    datestring TEXT := to_char(partition_date, 'YYYY-MM-DD');
BEGIN
    RAISE NOTICE '% Exporting sirivmpositions for date %', clock_timestamp(), partition_date::TEXT;

    PERFORM (SELECT COUNT(*)
             FROM aws_s3.query_export_to_s3(
                     format('SELECT
                                lower(concat_ws(''|'', s.operator_ref, s.line_name, s.journey_ref, s.date_of_journey)) as group_id,
                                to_json(s.recorded_at_time)#>>''{}'' as recorded_at_time,
                                to_json(s.response_time_stamp)#>>''{}'' as response_time_stamp,
                                s.latitude,
                                s.longitude,
                                s.line_name,
                                s.operator_ref,
                                s.vehicle_ref,
                                s.journey_ref,
                                s.direction_ref,
                                s.date_of_journey,
                                s.origin_ref,
                                s.destination_ref,
                                to_json(s.departure_time)#>>''{}'' as departure_time
                             FROM public."SiriVMPositions" s
                             WHERE date_of_journey = ''%s''::DATE
                             ORDER BY s.operator_ref, s.line_name, s.journey_ref, s.date_of_journey, s.direction_ref, s.vehicle_ref, s.recorded_at_time',
                            datestring),
                     aws_commons.create_s3_uri(
                             concat('abods-', SPLIT_PART(aurora_db_instance_identifier(), '-', 2), '-exporter-bucket'),
                             concat(
                                     'historic/csv/siri/YYYY=',
                                     DATE_PART('year', partition_date),
                                     '/MM=',
                                     LPAD(DATE_PART('month', partition_date)::TEXT, 2, '0'),
                                     '/siri_vm_',
                                     datestring,
                                     '.csv'
                             ),
                             'eu-west-2'),
                     options := 'format csv'
                  ));

    RAISE NOTICE '% Exported sirivmpositions for date %', clock_timestamp(), partition_date::TEXT;
END;
$$;

alter procedure historic_avl_export owner to abods_proxy_rw;
