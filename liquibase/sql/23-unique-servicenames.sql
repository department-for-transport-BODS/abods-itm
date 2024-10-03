CREATE TABLE if not exists public.expected_services_by_date (
	date_of_journey date not null,
	noc_and_line_and_servicecode text not null
);
CREATE INDEX if not exists expected_services_by_date_date_of_journey_idx ON public.expected_services_by_date USING btree (date_of_journey);
CREATE INDEX if not exists expected_services_by_date_noc_and_line_and_servicecode_idx ON public.expected_services_by_date USING btree (noc_and_line_and_servicecode);
alter table public.expected_services_by_date owner to abods_rw;

CREATE TABLE if not exists public.service_details (
	noc_and_line_and_servicecode text primary key,	
	operator_noc text,
	line_name text,
	service_name text NULL
);
CREATE INDEX if not exists expected_services_operator_noc ON public.service_details USING btree (operator_noc);
CREATE INDEX if not exists expected_services_line_name ON public.service_details USING btree (line_name);
alter table public.service_details owner to abods_rw;

drop table if exists expected_services;

create materialized view if not exists expected_services as
select distinct esbd.date_of_journey, 
sd.noc_and_line_and_servicecode,
sd.operator_noc,
sd.line_name,
sd.service_name
from expected_services_by_date esbd
left join service_details sd
on esbd.noc_and_line_and_servicecode = sd.noc_and_line_and_servicecode;
CREATE INDEX if not exists expected_services_date_of_journey_idx ON public.expected_services USING btree (date_of_journey);
CREATE INDEX if not exists expected_services_operator_noc_idx ON public.expected_services USING btree (operator_noc);
CREATE INDEX if not exists expected_services_line_name_idx ON public.expected_services USING btree (line_name);
CREATE INDEX if not exists expected_services_noc_and_line_and_servicecode_idx ON public.expected_services USING btree (noc_and_line_and_servicecode);
alter materialized view expected_services owner to abods_rw;


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
	day_of_week
)
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
	t.day_of_week
from "Timetable" t
left join transmodel_servicepattern ts 
on t.servicepattern_id = ts.id
where t.date_of_journey = partition_date
window w as (
	partition by t.group_id 
	order by t.stop_index asc 
	range between unbounded preceding and unbounded following
)
;

RAISE NOTICE 'Analysing expected journeys for for %', partition_date::text ;

analyse expected_journeys;

RAISE NOTICE 'Deleting expected_services_by_date for for %', partition_date::text ;

delete from expected_services_by_date where date_of_journey = partition_date;

RAISE NOTICE 'Inserting expected_services_by_date for for %', partition_date::text ;

insert into expected_services_by_date (
	date_of_journey,
	noc_and_line_and_servicecode
)
select distinct
date_of_journey,
noc_and_line_and_servicecode
from expected_journeys
where date_of_journey = partition_date;

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

