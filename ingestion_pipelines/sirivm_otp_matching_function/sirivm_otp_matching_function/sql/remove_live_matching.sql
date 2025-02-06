UPDATE public."Timetable" u
SET time_difference = NULL,
    actual_departure_time = NULL,
    otp_state = NULL,
    load_time_stamp = now()::timestamp(0),
    timestamp_after_estimate = NULL
FROM (VALUES %s) AS t(timetable_id, group_id)
WHERE u.timetable_id = t.timetable_id::bigint
  AND date_of_journey = now()::date
  AND u.group_id = t.group_id::text
RETURNING u.timetable_id;
