-- CREATE PERFORMANCE STATISTICS TABLE

CREATE TABLE IF NOT EXISTS performance_statistics(
	operator_noc text,
	line_name text,
	noc_and_line text,
	service_name text,
	is_timing_point boolean,
	date_period_start date,
	date_period_end date,
	period_type varchar(50),
	on_time_count integer,
	early_count integer,
	late_count integer,
	total_count integer,
	on_time_percentage decimal,
	trend_period_start date,
	trend_period_end date,
	trend_on_time_count integer,
	trend_early_count integer,
	trend_late_count integer,
	trend_total_count integer,
	trend_percentage decimal,
	percentage_change decimal,
	PRIMARY KEY (operator_noc, line_name, date_period_start, date_period_end, period_type)
);

-- CHANGE OWNERSHIP ---

alter table performance_statistics owner to abods_rw;

-- END --