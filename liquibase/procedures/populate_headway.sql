create or replace procedure populate_headway(IN pt_date date)
    language plpgsql
as
$$
DECLARE
    recent_stop_interval    INTERVAL    = INTERVAL '120' MINUTE;
    earliest_departure_time TIMESTAMPTZ = now() - recent_stop_interval;
BEGIN
    RAISE NOTICE '% Creating temp_timetable_headway', clock_timestamp();

    DROP TABLE IF EXISTS temp_timetable_headway;

    CREATE TABLE temp_timetable_headway AS
    SELECT
      *,
      extract(
        epoch
        FROM
          x.actual_departure_time - x.previous_actual_departure_time
      ) AS actual_headway
    FROM
      (
        SELECT
          timetable_id,
          COALESCE(actual_departure_time, timestamp_after_estimate) AS actual_departure_time,
          lag(
            COALESCE(actual_departure_time, timestamp_after_estimate)
          ) OVER (
            PARTITION BY operator_noc,
            line_name,
            date_of_journey,
            stop_id,
            stop_index
            ORDER BY
              stop_id,
              stop_index ASC,
              expected_departure_time ASC
          ) AS previous_actual_departure_time
        FROM
          public."Timetable"
        WHERE date_of_journey = pt_date
          AND expected_departure_time < earliest_departure_time
          AND previous_group_id IS NOT NULL
          AND (
            actual_departure_time IS NOT NULL
            OR timestamp_after_estimate IS NOT NULL
          )
      ) x
    WHERE
      x.previous_actual_departure_time IS NOT NULL;

    RAISE NOTICE '% Updating timetable table with headway data', clock_timestamp();

    UPDATE
      public."Timetable" y
    SET
      headway_time_difference = y.expected_headway - x.actual_headway,
      actual_headway = x.actual_headway
    FROM
      temp_timetable_headway x
    WHERE x.timetable_id = y.timetable_id
      AND y.date_of_journey = pt_date
      AND y.expected_departure_time < earliest_departure_time;

    RAISE NOTICE '% Dropping temp tables', clock_timestamp();

    DROP TABLE IF EXISTS temp_timetable_headway;

    RAISE NOTICE '% populate_headway complete', clock_timestamp();
END;
$$;

alter procedure populate_headway owner to abods_proxy_rw;
