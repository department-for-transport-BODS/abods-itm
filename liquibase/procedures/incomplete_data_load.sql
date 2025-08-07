create or replace procedure incomplete_data_load(IN partition_date date DEFAULT (CURRENT_DATE - '1 day'::interval))
    language plpgsql
as
$$
DECLARE
    recent_stop_interval    INTERVAL    = INTERVAL '120' MINUTE;
    earliest_departure_time TIMESTAMPTZ = now() - recent_stop_interval;
BEGIN
    RAISE NOTICE '% Start running incomplete_data_load ', clock_timestamp();

    RAISE NOTICE '% Creating stops without operator nocs table', clock_timestamp();

    CREATE TABLE incomplete_data_tmp_stops_without_operator_nocs AS
    SELECT
      timetable_id,
      vehiclejourney_id
    FROM
      public."Timetable" t
    WHERE t.date_of_journey = partition_date
      AND t.expected_departure_time < earliest_departure_time
      AND actual_departure_time IS NULL
      AND NOT EXISTS (
        SELECT
          1
        FROM
          public."Timetable" t2
          JOIN public."SiriVMPositions" s
            ON t2.operator_noc = s.operator_ref
        WHERE t2.timetable_id = t.timetable_id
          AND t2.date_of_journey = partition_date
          AND t2.expected_departure_time < earliest_departure_time
          AND s.date_of_journey = partition_date
      );

    RAISE NOTICE '% Creating stops without journey code table', clock_timestamp();

    CREATE TABLE incomplete_data_tmp_stops_without_journey_codes AS
    SELECT
      timetable_id,
      vehiclejourney_id
    FROM
      public."Timetable" t
    WHERE date_of_journey = partition_date
      AND actual_departure_time IS NULL
      AND expected_departure_time < (now() - recent_stop_interval)
      AND NOT EXISTS (
        SELECT
          1
        FROM
          public."Timetable" t2
          JOIN public."SiriVMPositions" s
            ON t2.group_id = s.group_id
            AND t2.direction = s.direction_ref
        WHERE t2.timetable_id = t.timetable_id
          AND t2.date_of_journey = partition_date
          AND t2.expected_departure_time < earliest_departure_time
          AND s.date_of_journey = partition_date
      )
      AND EXISTS (
        SELECT
          1
        FROM
          public."Timetable" t3
          JOIN public."SiriVMPositions" s
            ON t3.operator_noc = s.operator_ref
           AND t3.line_name = s.line_name
        WHERE t3.timetable_id = t.timetable_id
          AND t3.date_of_journey = partition_date
          AND t3.expected_departure_time < earliest_departure_time
          AND s.date_of_journey = partition_date
      );

    RAISE NOTICE '% Creating stops without service table', clock_timestamp();

    CREATE TABLE incomplete_data_tmp_stops_without_services AS
    SELECT
      t.timetable_id,
      vehiclejourney_id
    FROM
      public."Timetable" t
    WHERE t.date_of_journey = partition_date
      AND t.actual_departure_time IS NULL
      AND t.expected_departure_time < earliest_departure_time
      AND NOT EXISTS (
        SELECT
          1
        FROM
          public."Timetable" t2
          JOIN public."SiriVMPositions" s
            ON t.operator_noc = s.operator_ref
           AND t.line_name = s.line_name
           AND t.journey_code = s.journey_ref
        WHERE t2.timetable_id = t.timetable_id
          AND t2.date_of_journey = partition_date
          AND t2.expected_departure_time < earliest_departure_time
          AND s.date_of_journey = partition_date
      )
      AND NOT EXISTS (
        SELECT
          1
        FROM
          incomplete_data_tmp_stops_without_journey_codes
        WHERE timetable_id = t.timetable_id
      )
      AND EXISTS (
        SELECT
          1
        FROM
          public."Timetable" t3
          JOIN public."SiriVMPositions" s ON t3.operator_noc = s.operator_ref
        WHERE t3.timetable_id = t.timetable_id
          AND t3.date_of_journey = partition_date
          AND t3.expected_departure_time < earliest_departure_time
          AND s.date_of_journey = partition_date
      );

    RAISE NOTICE '% Creating stops with invalid gps in zone table', clock_timestamp();

    CREATE TABLE incomplete_data_tmp_stops_with_invalid_gps_in_zone AS
    SELECT
      DISTINCT timetable_id
    FROM
      public."Timetable" t
      JOIN public."SiriVMPositions" s
        ON t.operator_noc = s.operator_ref
       AND t.line_name = s.line_name
       AND t.journey_code = s.journey_ref
    WHERE t.date_of_journey = partition_date
      AND t.expected_departure_time < earliest_departure_time
      AND s.date_of_journey = partition_date
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
      ) * 1000 <= 70;

    RAISE NOTICE '% Creating stops without gps in zone table', clock_timestamp();

    CREATE TABLE incomplete_data_tmp_stops_without_gps_in_zone AS
    SELECT
      DISTINCT timetable_id
    FROM
      public."Timetable" t
      JOIN public."SiriVMPositions" s
        ON t.operator_noc = s.operator_ref
       AND t.line_name = s.line_name
       AND t.journey_code = s.journey_ref
    WHERE t.date_of_journey = partition_date
      AND t.expected_departure_time < earliest_departure_time
      AND s.date_of_journey = partition_date
      AND t.actual_departure_time IS NULL
      AND NOT EXISTS (
        SELECT
          1
        FROM
          incomplete_data_tmp_stops_with_invalid_gps_in_zone t2
        WHERE t2.timetable_id = t.timetable_id
      );

    RAISE NOTICE '% Populating incomplete reason column in timetable', clock_timestamp();

    UPDATE
      public."Timetable"
    SET
      incomplete_reason = 1
    WHERE timetable_id IN (
        SELECT
          timetable_id
        FROM
          incomplete_data_tmp_stops_without_operator_nocs
      )
      AND date_of_journey = partition_date;

    UPDATE
      public."Timetable"
    SET
      incomplete_reason = 2
    WHERE timetable_id IN (
        SELECT
          timetable_id
        FROM
          incomplete_data_tmp_stops_without_services
      )
      AND date_of_journey = partition_date;

    UPDATE
      public."Timetable"
    SET
      incomplete_reason = 3
    WHERE timetable_id IN (
        SELECT
          timetable_id
        FROM
          incomplete_data_tmp_stops_without_journey_codes
      )
      AND date_of_journey = partition_date;

    UPDATE
      public."Timetable"
    SET
      incomplete_reason = 4
    WHERE timetable_id IN (
        SELECT
          timetable_id
        FROM
          incomplete_data_tmp_stops_without_gps_in_zone
      )
      AND date_of_journey = partition_date;

    UPDATE
      public."Timetable"
    SET incomplete_reason = 5
    WHERE timetable_id IN (
        SELECT
          timetable_id
        FROM
          incomplete_data_tmp_stops_with_invalid_gps_in_zone
      )
      AND date_of_journey = partition_date;

    RAISE NOTICE '% Dropping temp tables', clock_timestamp();

    DROP TABLE
        incomplete_data_tmp_stops_without_operator_nocs,
        incomplete_data_tmp_stops_without_services,
        incomplete_data_tmp_stops_without_journey_codes,
        incomplete_data_tmp_stops_without_gps_in_zone,
        incomplete_data_tmp_stops_with_invalid_gps_in_zone;

    RAISE NOTICE '% incomplete_data_load complete', clock_timestamp();
END;
$$;

alter procedure incomplete_data_load owner to abods_proxy_rw;
