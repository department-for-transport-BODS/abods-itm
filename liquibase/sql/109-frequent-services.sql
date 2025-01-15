alter table timetable_summary_stops_tz
    add column if not exists frequent_service bool default FALSE;