UPDATE public."Timetable" u
SET time_difference = NULL,
    actual_departure_time = NULL,
    otp_state = NULL,
    load_time_stamp = now()::timestamp(0)
FROM (VALUES %s) AS t(timetable_id, group_id)
WHERE u.timetable_id = t.timetable_id::int
  AND date_of_journey = now()::date
  AND u.group_id = t.group_id
RETURNING load_time_stamp;