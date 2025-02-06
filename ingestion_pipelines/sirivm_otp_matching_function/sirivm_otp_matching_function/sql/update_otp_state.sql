UPDATE public."Timetable" u
SET otp_state = CASE
                    WHEN u.time_difference::int > 359 THEN 'Late'
                    WHEN (is_final_stop = 'Non-final'
                          AND u.time_difference::int < -60) THEN 'Early'
                    ELSE 'OnTime'
                END,
    load_time_stamp = now()::timestamp(0)
FROM (VALUES %s) AS t(timetable_id, time_difference, last_time_in_zone_utc, is_final_stop, journey_date, timestamp_after_estimate)
WHERE u.timetable_id = t.timetable_id::bigint
  AND date_of_journey = t.journey_date::date
  AND COALESCE (
              EXTRACT(epoch FROM (t.last_time_in_zone_utc::timestamp AT TIME ZONE 'UTC' - u.expected_departure_time)),
              EXTRACT(epoch FROM (t.timestamp_after_estimate::timestamp AT TIME ZONE 'UTC' - u.expected_departure_time)),
              0
      ) > -7200
RETURNING u.timetable_id;
