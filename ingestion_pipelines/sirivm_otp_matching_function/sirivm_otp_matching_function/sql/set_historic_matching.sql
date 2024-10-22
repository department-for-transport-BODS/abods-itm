-- Recalculating time difference when it's less than zero to make sure it's calculated correctly
UPDATE public."Timetable" u
SET time_difference = CASE
                          WHEN t.time_difference::int < 0 THEN extract(epoch
                                                                       FROM (t.last_time_in_zone_utc::timestamp AT TIME ZONE
                                                                              'UTC' - u.expected_departure_time::timestamp))::int
                          ELSE t.time_difference::int
                      END,
    actual_departure_time = t.last_time_in_zone_utc::timestamp AT TIME ZONE 'UTC',
    load_time_stamp = now()::timestamp(0)
FROM (VALUES %s) AS t(timetable_id, time_difference, last_time_in_zone_str, group_id, batch_id, last_time_in_zone_utc, otp_state, is_final_stop, journey_date)
WHERE u.timetable_id = t.timetable_id::int
  AND date_of_journey = t.journey_date::date
  AND COALESCE(
              EXTRACT(epoch FROM (t.last_time_in_zone_utc::timestamp AT TIME ZONE 'UTC' - u.expected_departure_time)),
              0
      ) > -7200
RETURNING u.timetable_id;
                    