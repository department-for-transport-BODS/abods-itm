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
      t1.timetable_id,
      COALESCE(EXTRACT(EPOCH FROM (
          COALESCE(t2.actual_departure_time, t2.timestamp_after_estimate) 
          - COALESCE(t1.actual_departure_time, t1.timestamp_after_estimate)
          )),0) as actual_headway,
      COALESCE(EXTRACT(EPOCH FROM (
          t2.expected_departure_time 
          - t1.expected_departure_time
          )),0) as expected_headway
      from public."Timetable" t1 left join public."Timetable" t2 
      on t1.previous_group_id = t2.group_id 
      and t1.stop_id = t2.stop_id and t1.stop_index = t2.stop_index 
      and t1.direction = t2.direction
      where t1.date_of_journey = pt_date
      and t2.date_of_journey = pt_date
      and t1.previous_group_id IS NOT NULL
      AND t1.expected_departure_time < earliest_departure_time;

    RAISE NOTICE '% Updating timetable table with headway data', clock_timestamp();

    UPDATE
      public."Timetable" y
    SET
      headway_time_difference = x.expected_headway - x.actual_headway,
      actual_headway = x.actual_headway
      expected_headway = x.expected_headway
    FROM
      temp_timetable_headway x
    WHERE x.timetable_id = y.timetable_id
      AND y.date_of_journey = pt_date;

    RAISE NOTICE '% Dropping temp tables', clock_timestamp();

    DROP TABLE IF EXISTS temp_timetable_headway;

    RAISE NOTICE '% populate_headway complete', clock_timestamp();
END;
$$;

alter procedure populate_headway owner to abods_proxy_rw;
