CREATE TABLE IF NOT EXISTS public.distinct_routes (
	id serial4 NOT NULL,
	route text NOT NULL,
	CONSTRAINT distinct_routes_pkey PRIMARY KEY (id),
	CONSTRAINT distinct_routes_unique UNIQUE (route)
);

alter table public.distinct_routes owner to abods_rw;

CREATE OR REPLACE PROCEDURE public.update_distinct_routes(IN partition_date date)
 LANGUAGE plpgsql
AS $procedure$
begin
RAISE NOTICE 'Updating distinct_routes for % at %', partition_date::text, current_timestamp::text ;

insert into
    public.distinct_routes (route)
select
    distinct string_agg(
        atco_code,
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

select cron.schedule('generate timetable', '05 15 * * *',  $$call update_all_transmodel_tables(); call update_all_naptan_tables(); call generate_timetable(current_date + 1); call generate_expected_tables(current_date + 1); call update_distinct_routes(current_date + 1);$$);

