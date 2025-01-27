UPDATE public."Timetable" u
SET time_difference = t.time_difference::int,
    actual_departure_time = t.last_time_in_zone_utc::timestamp AT TIME ZONE 'UTC',
    timestamp_after_estimate = t.timestamp_after_estimate::timestamp AT TIME ZONE 'UTC',
    otp_state = t.otp_state::TEXT,
    load_time_stamp = now()::timestamp(0)
FROM (VALUES %s) AS t(timetable_id, time_difference, last_time_in_zone_utc, otp_state, timestamp_after_estimate, date_of_journey)
WHERE u.timetable_id = t.timetable_id::bigint
  AND date_of_journey = t.date_of_journey::date
RETURNING u.timetable_id;