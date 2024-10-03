--- CREATE AND INDEX TIMETABLE SUMMARY BY SERVICES

CREATE TABLE IF NOT EXISTS public.timetable_summary_service
(
    timetable_id bigserial NOT NULL,
    operator_noc text NOT NULL,
	line_name text NOT NULL,
	noc_and_line text NOT NULL,
	service_name text NOT NULL,
    date_of_journey date NOT NULL,
    departure_hour time NOT NULL,
    day_of_week integer NOT NULL,
    on_time_count integer,
    early_count integer,
    late_count integer,
    completed integer,
    scheduled integer,
    is_timing_point boolean NOT NULL,
    max_early integer NOT NULL,
    max_late integer NOT NULL,
    avg_time_difference double precision,
    PRIMARY KEY (line_name, noc_and_line, service_name, operator_noc, date_of_journey, day_of_week, departure_hour, is_timing_point, max_early, max_late)
)PARTITION BY RANGE (date_of_journey);

-- CHANGE OWNERSHIP

alter table timetable_summary_operator owner to abods_rw;

-- CREATE INDEXES ON THE TABLE

CREATE INDEX opt    ON timetable_summary_service (operator_noc); 
CREATE INDEX dwt    ON timetable_summary_service (day_of_week);
CREATE INDEX istt    ON timetable_summary_service (is_timing_point);     
CREATE INDEX nolt    ON timetable_summary_service (noc_and_line);
CREATE INDEX dpt    ON timetable_summary_service (departure_hour);
CREATE INDEX lnt    ON timetable_summary_service (line_name);
CREATE INDEX mxet    ON timetable_summary_service (max_early);
CREATE INDEX mltt    ON timetable_summary_service (max_late);

-- END-----
