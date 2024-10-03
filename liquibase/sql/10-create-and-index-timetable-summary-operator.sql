-- CREATE AND INDEX timetable_summary_operator

CREATE TABLE IF NOT EXISTS public.timetable_summary_operator
(
  timetable_id bigserial NOT NULL,
  operator_noc text NOT NULL,
  date_of_journey date NOT NULL,
	departure_hour time,
  day_of_week integer,
	on_time_count integer, 
	early_count integer, 
	late_count integer, 
	completed integer, 
	scheduled integer, 
  is_timing_point boolean,
	max_early integer,
	max_late integer,
	avg_time_difference decimal,
  PRIMARY KEY (operator_noc, date_of_journey, day_of_week, departure_hour, is_timing_point, max_early, max_late)
)PARTITION BY RANGE (date_of_journey);

-- CHANGE OWNER TO abods_rw

alter table timetable_summary_operator owner to abods_rw;

-- CREATE INDEXES ON operator_noc, day_of_week AND is_timing_point

CREATE INDEX op   ON timetable_summary_operator (operator_noc); 
CREATE INDEX dw   ON timetable_summary_operator (day_of_week);
CREATE INDEX ist  ON timetable_summary_operator (is_timing_point);

