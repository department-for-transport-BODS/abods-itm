ALTER TABLE timetable_summary_stops_tz
ADD COLUMN direction varchar(20),
ADD COLUMN stop_index int,
ADD COLUMN count_delayed int,
ADD COLUMN average_delay numeric,
ADD COLUMN diff_sched_time_to_stop numeric,
ADD COLUMN diff_sched_time_to_stop_timing_point numeric,
ADD COLUMN diff_actual_time_to_stop numeric,
ADD COLUMN diff_actual_time_to_stop_timing_point numeric;     

ALTER TABLE timetable_summary_operator_t
ADD COLUMN count_delayed int,
ADD COLUMN average_delay numeric; 

ALTER TABLE timetable_summary_service_tz
ADD COLUMN direction varchar(20),
ADD COLUMN count_delayed int,
ADD COLUMN average_delay numeric; 