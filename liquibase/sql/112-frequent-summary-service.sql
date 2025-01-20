CREATE TABLE IF NOT EXISTS public.timetable_frequent_summary_services
(
    timetable_id                 bigserial 				  PRIMARY KEY,
    operator_noc                 text                     NOT NULL,
    service_code                 text                     NOT NULL,
    noc_and_line_and_servicecode text                     NOT NULL,
    line_name                    text                     NOT NULL,
    date_of_journey              date                     NOT NULL,
    departure_hour               timestamp with time zone NOT NULL,
    departure_hour_only          time with time zone      NOT NULL,
    day_of_week                  integer                  NOT NULL,
    max_early                    integer                  NOT NULL,
    max_late                     integer                  NOT NULL,
    avg_time_difference          numeric				  NOT NULL,
    expected_headway             numeric				  NOT NULL,
    actual_headway               numeric				  NOT NULL,
    excess_wait_time             numeric				  NOT NULL,
	headway_stops_count			 numeric				  NOT NULL,
    estimated                    boolean                  NOT NULL,
    CONSTRAINT timetable_frequent_summary_services_unique UNIQUE (service_code, operator_noc, date_of_journey,
                                                                     day_of_week, departure_hour, departure_hour_only,
                                                                     max_early, max_late, noc_and_line_and_servicecode)
) PARTITION BY RANGE (date_of_journey);

ALTER TABLE IF EXISTS public.timetable_frequent_summary_services
    OWNER to abods_proxy_rw;

CREATE INDEX IF NOT EXISTS date_of_journey_stopstz
    ON public.timetable_frequent_summary_services USING btree
        (date_of_journey ASC NULLS LAST);


CREATE INDEX IF NOT EXISTS day_of_week_stopstz
    ON public.timetable_frequent_summary_services USING btree
        (day_of_week ASC NULLS LAST);


CREATE INDEX IF NOT EXISTS departure_hour_only_stopstz
    ON public.timetable_frequent_summary_services USING btree
        (departure_hour_only ASC NULLS LAST);


CREATE INDEX IF NOT EXISTS departure_hour_stopstz
    ON public.timetable_frequent_summary_services USING btree
        (departure_hour ASC NULLS LAST);

CREATE INDEX IF NOT EXISTS max_early_stopstz
    ON public.timetable_frequent_summary_services USING btree
        (max_early ASC NULLS LAST);


CREATE INDEX IF NOT EXISTS max_late_stopstz
    ON public.timetable_frequent_summary_services USING btree
        (max_late ASC NULLS LAST);


CREATE INDEX IF NOT EXISTS noc_and_line_and_servicecode_stopstz
    ON public.timetable_frequent_summary_services USING btree
        (noc_and_line_and_servicecode ASC NULLS LAST);


CREATE INDEX IF NOT EXISTS operator_noc_stopstz
    ON public.timetable_frequent_summary_services USING btree
        (operator_noc ASC NULLS LAST);


CREATE INDEX IF NOT EXISTS service_code_stopstz
    ON public.timetable_frequent_summary_services USING btree
        (service_code ASC NULLS LAST);