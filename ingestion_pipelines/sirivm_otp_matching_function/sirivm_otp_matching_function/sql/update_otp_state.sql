update  public."Timetable" u
set
    otp_state = case when u.time_difference::int > 359 then 'Late' when (is_final_stop = 'Non-final' and u.time_difference::int < -60) then 'Early' else 'OnTime' end,
    load_time_stamp = now()::timestamp(0)
from (values %s) as t(time_difference, last_time_in_zone_str, timetable_id, group_id, batch_id, last_time_in_zone_utc, otp_state, is_final_stop, journey_date)
where u.timetable_id = t.timetable_id::int and date_of_journey = t.journey_date::date and coalesce(extract (epoch from (t.last_time_in_zone_utc::timestamp at TIME zone 'utc' - u.expected_departure_time)),0) > -7200;