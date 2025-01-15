alter table timetable_summary_service_tz drop column IF EXISTS headway_valid;


alter table timetable_summary_stops_tz drop column IF EXISTS frequent_service;

alter table timetable_summary_stops_tz drop column IF EXISTS headway_stops_count;

alter table timetable_summary_stops_tz drop column IF EXISTS expected_headway;

alter table timetable_summary_stops_tz drop column IF EXISTS actual_headway;
