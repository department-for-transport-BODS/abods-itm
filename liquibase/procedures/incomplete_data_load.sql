create or replace procedure incomplete_data_load(IN partition_date date DEFAULT (CURRENT_DATE - '1 day'::interval))
    language plpgsql
as
$$
DECLARE
    next_date            DATE     = partition_date + INTERVAL '1' DAY;
    recent_stop_interval INTERVAL = INTERVAL '120' MINUTE;
BEGIN
    RAISE NOTICE '% Start running incomplete_data_load ', clock_timestamp();

    RAISE NOTICE '% Creating stops without operator nocs table', clock_timestamp();

    CREATE TEMP TABLE incomplete_data_tmp_stops_wo_nocs AS
    SELECT
      timetable_id
    FROM
      public."Timetable" t
    WHERE
      date_of_journey = partition_date
      AND expected_departure_time < (now() - recent_stop_interval)
      AND actual_departure_time IS NULL
      AND NOT EXISTS (
        SELECT
          1
        FROM
          public."Timetable" t2
          JOIN public."SiriVMPositions" s ON t2.operator_noc = s.operator_ref
        WHERE
          t2.timetable_id = t.timetable_id
          AND t2.date_of_journey = partition_date
          AND (s.date_of_journey = partition_date OR s.date_of_journey = next_date)
      );

    RAISE NOTICE '% Created stops without operator nocs table', clock_timestamp();

    RAISE NOTICE '% Creating stops without journey code table', clock_timestamp();

    CREATE TEMP TABLE incomplete_data_tmp_stops_wo_journey_code AS
    SELECT
      timetable_id
    FROM
      public."Timetable" t
    WHERE
      date_of_journey = partition_date
      AND actual_departure_time IS NULL
      AND expected_departure_time < (now() - recent_stop_interval)
      AND NOT EXISTS (
        SELECT
          1
        FROM
          public."Timetable" t2
          JOIN public."SiriVMPositions" s
            ON t.operator_noc = s.operator_ref
           AND t.line_name = s.line_name
           AND t.journey_code = s.journey_ref
        WHERE
          t2.timetable_id = t.timetable_id
          AND t2.date_of_journey = partition_date
          AND (s.date_of_journey = partition_date OR s.date_of_journey = next_date)
      )
      AND EXISTS (
        SELECT
          1
        FROM
          public."Timetable" t3
          JOIN public."SiriVMPositions" s ON t3.operator_noc = s.operator_ref
          AND t3.line_name = s.line_name
        WHERE
          t3.timetable_id = t.timetable_id
          AND t3.date_of_journey = partition_date
          AND (s.date_of_journey = partition_date OR s.date_of_journey = next_date)
      );

    RAISE NOTICE '% Created stops without journey code table', clock_timestamp();

    RAISE NOTICE '% Creating stops without service table', clock_timestamp();

    CREATE TEMP TABLE incomplete_data_tmp_stops_wo_service AS
    SELECT
      timetable_id
    FROM
      public."Timetable" t
    WHERE
      date_of_journey = partition_date
      AND actual_departure_time IS NULL
      AND expected_departure_time < (now() - recent_stop_interval)
      AND NOT EXISTS (
        SELECT
          1
        FROM
          public."Timetable" t2
          JOIN public."SiriVMPositions" s
            ON t.operator_noc = s.operator_ref
           AND t.line_name = s.line_name
           AND t.journey_code = s.journey_ref
        WHERE
          t2.timetable_id = t.timetable_id
          AND t2.date_of_journey = partition_date
          AND (s.date_of_journey = partition_date OR s.date_of_journey = next_date)
      )
      AND NOT EXISTS (
        SELECT
          1
        FROM
          incomplete_data_tmp_stops_wo_journey_code
        WHERE
          timetable_id = t.timetable_id
      )
      AND EXISTS (
        SELECT
          1
        FROM
          public."Timetable" t3
          JOIN public."SiriVMPositions" s ON t3.operator_noc = s.operator_ref
        WHERE
          t3.timetable_id = t.timetable_id
          AND t3.date_of_journey = partition_date
          AND s.date_of_journey = partition_date
      );

    RAISE NOTICE '% Created stops without service table',
        clock_timestamp();

    RAISE NOTICE '% Creating stops with invalid gps in zone table',
        clock_timestamp();

    CREATE TEMP TABLE incomplete_data_tmp_stops_w_invalid_gps_in_zone AS (
      SELECT
        DISTINCT timetable_id
      FROM
        public."Timetable" t
        JOIN public."SiriVMPositions" s
          ON t.operator_noc = s.operator_ref
         AND t.line_name = s.line_name
         AND t.journey_code = s.journey_ref
      WHERE
        t.date_of_journey = partition_date
        AND t.expected_departure_time < (now() - recent_stop_interval)
        AND (s.date_of_journey = partition_date OR s.date_of_journey = next_date)
        AND t.actual_departure_time IS NULL
        AND (
          2 * ASIN(
            SQRT(
              POWER(
                SIN(
                  (RADIANS(t.stop_latitude) - RADIANS(s.latitude)) / 2
                ),
                2
              ) + COS(RADIANS(s.latitude)) * COS(RADIANS(t.stop_latitude)) * POWER(
                SIN(
                  (RADIANS(s.longitude) - RADIANS(t.stop_longitude)) / 2
                ),
                2
              )
            )
          ) * 6371
        ) * 1000 <= 70
    );

    RAISE NOTICE '% Created stops with invalid gps in zone table', clock_timestamp();

    RAISE NOTICE '% Creating stops without gps in zone table', clock_timestamp();

    CREATE TEMP TABLE incomplete_data_tmp_stops_wo_gps_in_zone AS
    SELECT
      DISTINCT timetable_id
    FROM
      public."Timetable" t
      JOIN public."SiriVMPositions" s
        ON t.operator_noc = s.operator_ref
       AND t.line_name = s.line_name
       AND t.journey_code = s.journey_ref
    WHERE
      t.date_of_journey = partition_date
      AND t.expected_departure_time < (now() - recent_stop_interval)
      AND (s.date_of_journey = partition_date OR s.date_of_journey = next_date)
      AND t.actual_departure_time IS NULL
      AND NOT EXISTS (
        SELECT
          1
        FROM
          incomplete_data_tmp_stops_w_invalid_gps_in_zone t2
        WHERE
          t2.timetable_id = t.timetable_id
      );

    RAISE NOTICE '% Created stops without gps in zone table',
        clock_timestamp();

    RAISE NOTICE '% Populating incomplete reason column in timetable',
        clock_timestamp();

    UPDATE
      public."Timetable"
    SET
      incomplete_reason = 1
    WHERE
      timetable_id IN (
        SELECT
          timetable_id
        FROM
          incomplete_data_tmp_stops_wo_nocs
      )
      AND date_of_journey = partition_date;

    UPDATE
      public."Timetable"
    SET
      incomplete_reason = 2
    WHERE
      timetable_id IN (
        SELECT
          timetable_id
        FROM
          incomplete_data_tmp_stops_wo_service
      )
      AND date_of_journey = partition_date;

    UPDATE
      public."Timetable"
    SET
      incomplete_reason = 3
    WHERE
      timetable_id IN (
        SELECT
          timetable_id
        FROM
          incomplete_data_tmp_stops_wo_journey_code
      )
      AND date_of_journey = partition_date;

    UPDATE
      public."Timetable"
    SET
      incomplete_reason = 4
    WHERE
      timetable_id IN (
        SELECT
          timetable_id
        FROM
          incomplete_data_tmp_stops_wo_gps_in_zone
      )
      AND date_of_journey = partition_date;

    UPDATE
      public."Timetable"
    SET
      incomplete_reason = 5
    WHERE
      timetable_id IN (
        SELECT
          timetable_id
        FROM
          incomplete_data_tmp_stops_w_invalid_gps_in_zone
      )
      AND date_of_journey = partition_date;

    RAISE NOTICE '% incomplete_data_load complete', clock_timestamp();
END;
$$;

alter procedure incomplete_data_load owner to abods_proxy_rw;
