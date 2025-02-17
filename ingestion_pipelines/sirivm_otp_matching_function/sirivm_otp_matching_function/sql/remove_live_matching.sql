UPDATE public."Timetable" u
SET time_difference = NULL,
    actual_departure_time = NULL,
    otp_state = NULL,
    load_time_stamp = now()::timestamp(0),
    timestamp_after_estimate = NULL
FROM (VALUES %s) AS t(timetable_id, journey_date, alternate_journey_date)
WHERE u.timetable_id = t.timetable_id::bigint
  AND date_of_journey IN (t.journey_date::date, t.alternate_journey_date::date)
RETURNING u.timetable_id;
