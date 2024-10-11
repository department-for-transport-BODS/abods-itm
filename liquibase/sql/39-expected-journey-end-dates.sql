alter table if exists public.expected_journeys
add column if not exists expected_journey_end timestamptz;

CREATE OR REPLACE PROCEDURE public.generate_expected_tables(IN partition_date date)
 LANGUAGE plpgsql
AS $procedure$
begin
RAISE NOTICE 'Deleting expected journeys for %', partition_date::text ;

delete from expected_journeys where date_of_journey = partition_date;

RAISE NOTICE 'Inserting expected journeys for for %', partition_date::text ;

insert into expected_journeys (
	date_of_journey,
	operator_noc,
	line_name,
	noc_and_line_and_servicecode,
	journey_code,
	group_id,
	stop_count,
	expected_journey_start,
	journey_pattern_description,
	vehicle_journey_id,
	day_of_week,
	admin_area_id,
	expected_journey_end
)
with journeys as (
	select distinct
		t.date_of_journey,
		t.operator_noc,
		t.line_name,
		concat(t.operator_noc, '-', t.line_name,'-',t.service_code) as noc_and_line_and_servicecode,
		t.journey_code,
		t.group_id,
		count(stop_index) over w as stop_count,
		first_value(t.expected_departure_time) over w as start_time,
		ts.description as journey_pattern_description,
		t.vehiclejourney_id,
		t.day_of_week,
		t.admin_area_id,
		last_value(t.expected_departure_time) over w as end_time
	from "Timetable" t 
	left join transmodel_servicepattern ts 
	on t.servicepattern_id = ts.id
	where t.date_of_journey = partition_date
	window w as (
		partition by t.group_id 
		order by t.stop_index asc 
		range between unbounded preceding and unbounded following
	)
)
select 
	date_of_journey,
	operator_noc,
	line_name,
	noc_and_line_and_servicecode,
	journey_code,
	group_id,
	stop_count,
	start_time,
	journey_pattern_description,
	vehiclejourney_id,
	day_of_week,
	array_agg(admin_area_id) as admin_area_id,
	end_time
from journeys
group by 
	date_of_journey,
	operator_noc,
	line_name,
	noc_and_line_and_servicecode,
	journey_code,
	group_id,
	stop_count,
	start_time,
	journey_pattern_description,
	vehiclejourney_id,
	day_of_week,
	end_time
;

RAISE NOTICE 'Analysing expected journeys for for %', partition_date::text ;

analyse expected_journeys;

RAISE NOTICE 'Deleting expected_services_by_date for for %', partition_date::text ;

delete from expected_services_by_date where date_of_journey = partition_date;

RAISE NOTICE 'Inserting expected_services_by_date for for %', partition_date::text ;

insert into expected_services_by_date (
	date_of_journey,
	noc_and_line_and_servicecode,
	admin_area_id
)
select
date_of_journey,
noc_and_line_and_servicecode,
array_agg(admin_area_id) as admin_area_id
from (
select distinct
date_of_journey,
noc_and_line_and_servicecode,
unnest(admin_area_id) as admin_area_id
from expected_journeys
where date_of_journey = partition_date)
group by 
date_of_journey,
noc_and_line_and_servicecode;

RAISE NOTICE 'Analysing expected_services_by_date  for %', partition_date::text ;

analyse expected_services_by_date;

RAISE NOTICE 'Upserting service_details for %', partition_date::text ;

insert into service_details (
noc_and_line_and_servicecode,
operator_noc,
line_name,
service_name
)
select distinct
noc_and_line_and_servicecode,
operator_noc,
line_name,
first_value(journey_pattern_description) over (partition by date_of_journey, operator_noc, line_name, noc_and_line_and_servicecode order by stop_count desc, journey_pattern_description asc) as service_name
from expected_journeys
where date_of_journey = partition_date
on conflict (noc_and_line_and_servicecode)
do update set (
operator_noc,
line_name,
service_name
) = (
EXCLUDED.operator_noc,
EXCLUDED.line_name,
EXCLUDED.service_name
);

RAISE NOTICE 'Analysing service_details for for %', partition_date::text ;

analyse service_details;

RAISE NOTICE 'Refreshing expected_services for for %', partition_date::text ;

refresh materialized view expected_services;

RAISE NOTICE 'Deleting expected operators for for %', partition_date::text ;

delete from expected_operators where date_of_journey = partition_date;

RAISE NOTICE 'Inserting expected operators for for %', partition_date::text ;

insert into expected_operators (
	date_of_journey,
	operator_noc,
	operator_name
)
select distinct es.date_of_journey, es.operator_noc, o."name"
from expected_services es
left join traveline_operators o on
o.noc_code = es.operator_noc
where es.date_of_journey = partition_date;

RAISE NOTICE 'Analysing expected operators for for %', partition_date::text ;

analyse expected_operators;

RAISE NOTICE 'Done';

end; $procedure$
;

ALTER PROCEDURE public.generate_expected_tables
    OWNER TO abods_proxy_rw;


CREATE OR REPLACE PROCEDURE public.update_distinct_routes(IN partition_date date)
 LANGUAGE plpgsql
AS $procedure$
begin
RAISE NOTICE 'Updating distinct_routes for % at %', partition_date::text, current_timestamp::text ;

insert into
    public.distinct_routes (route)
select
    distinct string_agg(
        stop_id::text,
        ','
        order by
            expected_departure_time asc,
            stop_index asc
    )
from
    public."Timetable"
where
    date_of_journey = partition_date
group by
    group_id on conflict (route) do nothing;

RAISE NOTICE 'Analysing distinct_routes at %' , current_timestamp::text ;

analyse public.distinct_routes;

RAISE NOTICE 'Done';

end; $procedure$
;


ALTER PROCEDURE public.update_distinct_routes owner to abods_rw;

CREATE TABLE if not exists public.corridor (
	corridor_id bigserial NOT NULL,
	corridor_name text NULL,
	organisation_id int8 NULL,
	user_id int8 NULL
);

alter table public.corridor owner to abods_rw;

CREATE TABLE if not exists public.corridor_stops (
	corridor_index int8 NULL,
	corridor_id int8 NULL,
	stop_id int8 NULL,
	route_to_next_stop text NULL,
	distance_to_next_stop int4 NULL
);

alter table public.corridor_stops owner to abods_rw;


CREATE INDEX if not exists  index_on_stop_id 
	ON public."Timetable" (stop_id); 