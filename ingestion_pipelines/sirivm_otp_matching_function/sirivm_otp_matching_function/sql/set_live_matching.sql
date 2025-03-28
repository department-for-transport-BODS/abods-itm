UPDATE public."Timetable" u
SET time_difference = t.time_difference::int,
    actual_departure_time = t.last_time_in_zone_utc::timestamp AT TIME ZONE 'UTC',
    timestamp_after_estimate = t.timestamp_after_estimate::timestamp AT TIME ZONE 'UTC',
    -- When passengers aren't being picked up, we don't consider it early
    otp_state = CASE WHEN (u.set_down IS NOT NULL AND u.set_down AND t.otp_state = 'Early') THEN 'OnTime' ELSE t.otp_state::TEXT END,
    load_time_stamp = now()::timestamp(0)
FROM (VALUES %s) AS t(timetable_id, time_difference, last_time_in_zone_utc, otp_state, timestamp_after_estimate, journey_date, alternate_journey_date)
WHERE u.timetable_id = t.timetable_id::bigint
  AND date_of_journey IN (t.journey_date::date, t.alternate_journey_date::date)
RETURNING u.timetable_id;
