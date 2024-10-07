update  public."Timetable" u
set
    time_difference = t.time_difference::int,
    actual_departure_time = t.last_time_in_zone_utc::timestamp at TIME zone 'utc',
    otp_state = t.otp_state::TEXT,
    load_time_stamp = now()::timestamp(0)
from (values %s) as t(time_difference, last_time_in_zone_str, timetable_id, group_id, batch_id, last_time_in_zone_utc, otp_state, is_final_stop)
where u.timetable_id = t.timetable_id::int and date_of_journey = now()::date and coalesce(extract (epoch from (t.last_time_in_zone_utc::timestamp at TIME zone 'utc' - u.expected_departure_time)),0) > -7200;