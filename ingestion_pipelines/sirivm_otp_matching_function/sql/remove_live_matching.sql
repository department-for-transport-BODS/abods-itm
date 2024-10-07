update  public."Timetable" u
set
    time_difference = null,
    actual_departure_time = null,
    otp_state = null,
    load_time_stamp = now()::timestamp(0)
from (values %s) as t(stop_ind, timetable_id, group_id)
where u.timetable_id = t.timetable_id::int and date_of_journey = now()::date and u.group_id = t.group_id and u.stop_index = t.stop_ind::int;
                