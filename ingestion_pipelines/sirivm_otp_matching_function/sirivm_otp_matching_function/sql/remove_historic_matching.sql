UPDATE public."Timetable" u
SET time_difference = NULL,
    actual_departure_time = NULL,
    otp_state = NULL,
    load_time_stamp = now()::timestamp(0)
FROM (VALUES %s) AS t(timetable_id, group_id, journey_date)
WHERE u.timetable_id = t.timetable_id::int
  AND date_of_journey = t.journey_date::date
  AND u.group_id = t.group_id
RETURNING u.timetable_id;