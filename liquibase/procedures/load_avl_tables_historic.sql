create or replace procedure load_avl_tables_historic(IN pt_date date)
    language plpgsql
as
$$
DECLARE
    partition_date date := pt_date;
    tablename      text;

BEGIN
    tablename := 'SiriVMPositions_p' || to_char(partition_date, 'YYYY_MM_DD');

    EXECUTE format(
            'CREATE TABLE IF NOT EXISTS public.%I PARTITION OF public."SiriVMPositions" FOR VALUES FROM (%L) TO (%L)',
            tablename,
            partition_date,
            partition_date + interval '1' day
            );

    EXECUTE format('ALTER TABLE public.%I OWNER TO abods_rw', tablename);

    EXECUTE format('
                  INSERT INTO
                  public.%I (
                    operator_ref,
                    line_name,
                    journey_ref,
                    date_of_journey,
                    direction_ref,
                    recorded_at_time,
                    response_time_stamp,
                    Latitude,
                    Longitude,
                    vehicle_ref,
                    batch_id,
                    group_id
                  )
                SELECT
                  operator_ref,
                  coalesce(line_name, ''''),
                  journey_ref,
                  date_of_journey,
                  direction_ref,
                  recorded_at_time::timestamp(0) AT TIME ZONE ''UTC'',
                  response_timestamp::timestamp(0) AT TIME ZONE ''UTC'',
                  latitude::real,
                  longitude::real,
                  vehicle_ref,
                  batch_id,
                  LOWER(
                    concat_ws(
                      ''|'',
                      operator_ref,
                      coalesce(line_name, ''''),
                      journey_ref,
                      to_char(date_of_journey, ''YYYY-MM-DD'')
                    )
                  ) AS group_id
                FROM
                  public.staging_avl_positions_historic pos
                WHERE
                  date_of_journey = %L ON CONFLICT DO NOTHING;
                ', tablename, partition_date);

    INSERT INTO
      public.latest_vehicle_positions(
        operator_ref,
        vehicle_ref,
        line_name,
        journey_ref,
        direction_ref,
        recorded_at_time,
        latitude,
        longitude,
        group_id
      )
    SELECT
      operator_ref AS operator_ref,
      vehicle_ref AS vehicle_ref,
      coalesce(line_name, '') AS line_name,
      journey_ref AS journey_ref,
      direction_ref AS direction_ref,
      recorded_at_time::timestamp(0) AT TIME ZONE 'UTC' AS recorded_at_time,
      latitude::real AS latitude,
      longitude::real AS longitude,
      LOWER(
        concat_ws(
          '|',
          operator_ref,
          coalesce(line_name, ''),
          journey_ref,
          to_char(date_of_journey, 'YYYY-MM-DD')
        )
      ) AS group_id
    FROM
      public.staging_avl_positions_historic ON CONFLICT (
        operator_ref,
        vehicle_ref
      ) DO
    UPDATE
    SET
      line_name = EXCLUDED.line_name,
      journey_ref = EXCLUDED.journey_ref,
      direction_ref = EXCLUDED.direction_ref,
      recorded_at_time = EXCLUDED.recorded_at_time,
      latitude = EXCLUDED.latitude,
      longitude = EXCLUDED.longitude,
      group_id = EXCLUDED.group_id;

    TRUNCATE public.staging_avl_positions_historic;

END;
$$;

alter procedure load_avl_tables_historic owner to abods_proxy_rw;
