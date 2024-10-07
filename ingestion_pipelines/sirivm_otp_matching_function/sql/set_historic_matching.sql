-- Recalculating time difference when it's less than zero to make sure it's calculated correctly
update  public."Timetable" u
set
    time_difference = case when t.time_difference::int < 0 then extract(epoch from (t.last_time_in_zone_utc::timestamp at TIME zone 'utc' - u.expected_departure_time::timestamp))::int else t.time_difference::int end,
    actual_departure_time = t.last_time_in_zone_utc::timestamp at TIME zone 'utc',
    load_time_stamp = now()::timestamp(0)
from (values %s) as t(time_difference, last_time_in_zone_str, timetable_id, group_id, batch_id, last_time_in_zone_utc, otp_state, is_final_stop, journey_date)
where u.timetable_id = t.timetable_id::int and date_of_journey = t.journey_date::date and coalesce(extract (epoch from (t.last_time_in_zone_utc::timestamp at TIME zone 'utc' - u.expected_departure_time)),0) > -7200;
                    