CREATE TABLE IF NOT EXISTS public.feed_monitor_minute_summary (
	id bigserial NOT NULL,
	date_of_journey date NOT NULL,
	operator_noc text NOT NULL,
	received_interval timestamptz NOT NULL,
	expected int4 NOT NULL,
	actual int4 NOT NULL,
	live_locations int4 NOT NULL,
	CONSTRAINT feed_monitor_minute_summary PRIMARY KEY (id, date_of_journey)
)
PARTITION BY RANGE (date_of_journey);

create index if not exists feed_monitor_minute_summary_operator_noc_idx on public.feed_monitor_minute_summary (operator_noc);
create index if not exists feed_monitor_minute_summary_received_interval_idx on public.feed_monitor_minute_summary (received_interval);

alter table public.feed_monitor_minute_summary owner to abods_rw;

CREATE TABLE IF NOT EXISTS public.feed_monitor_hourly_summary (
	id bigserial NOT NULL,
	operator_noc text NOT NULL,
	received_interval timestamptz NOT NULL,
	expected int4 NOT NULL,
	actual int4 NOT NULL,
	CONSTRAINT feed_monitor_hourly_summary_pk PRIMARY KEY (id)
);

alter table public.feed_monitor_hourly_summary owner to abods_rw;

create table if not exists public.feed_monitor_summary (
	id bigserial NOT NULL,
	operator_noc text UNIQUE NOT NULL,
	last_outage timestamptz,
	unavailable_since timestamptz,
	update_frequency int,
	availability numeric,
	CONSTRAINT feed_monitor_summary_pk PRIMARY KEY (id)
);

alter table public.feed_monitor_summary owner to abods_rw;

create table if not exists public.feed_monitor_daily_summary (
	id bigserial NOT NULL,
	date_of_journey date not null,
	operator_noc text NOT NULL,
	update_frequency int,
	availability numeric,
	CONSTRAINT feed_monitor_daily_summary_pk PRIMARY KEY (id)
);

alter table public.feed_monitor_daily_summary owner to abods_rw;

CREATE OR REPLACE PROCEDURE public.generate_feed_monitoring_data(
	IN start_point timestamptz DEFAULT (date_trunc('hour', now()) - interval '1 hour'),
	IN whole_day boolean DEFAULT false)
 LANGUAGE plpgsql
AS $procedure$
declare
	start_hour TIMESTAMPTZ;
    end_hour TIMESTAMPTZ;
    start_time TIMESTAMPTZ;
    end_time TIMESTAMPTZ;
	hourly_rollup_period_start timestamptz := date_trunc('hour', current_timestamp) - interval '24 hours';
	hourly_rollup_period_end timestamptz := date_trunc('hour', current_timestamp);
	f RECORD;
begin
	
	--
	-- set boundaries to day if whole_day is true else hour if false
	--

	if whole_day = true then
		if date_trunc('day', start_point)::date = current_date then 
			start_hour := date_trunc('day', start_point);
			end_hour = date_trunc('hour', start_point) + interval '1 hour'; -- start at the start of day and go to the last hour or hour specified
		else
			start_hour := date_trunc('day', start_point);
			end_hour := start_hour + interval '1 day'; -- start at the start of the specified day and go to end
		end if;
	else
		start_hour := date_trunc('hour', start_point); -- start at the specified hour or last hour and go to end of that hour
		end_hour := start_hour + interval '1 hour'; 
	end if;

	--
	-- loop through the hours between boundaries generating per-minute stats for the hour
	--  
	
	RAISE NOTICE 'Getting expected journeys by hour between % and %', start_hour, end_hour;

	for f in select generate_series(start_hour, end_hour - interval '1 minute', INTERVAL '1 hour') loop 
		start_time := f;
		end_time := start_time + interval '1 hour';
	
		RAISE NOTICE 'Getting expected journeys for start time = %, End time = %', start_time, end_time;
		
		--
		-- create temp table with stats for expected journeys
		--
		
		RAISE NOTICE 'Creating feedmon_temp_expected_journeys for start time = %, End time = %', start_time, end_time;
	
		drop table if exists feedmon_temp_expected_journeys;
	
		create temporary table feedmon_temp_expected_journeys as
			select DISTINCT
				ej.operator_noc,
				ej.group_id,
				ej.expected_journey_start,
				case 
					when ej.expected_journey_end < ej.expected_journey_start
					then ej.expected_journey_end + interval '1 day'
					else ej.expected_journey_end
				end as expected_journey_end -- todo case can be removed when departure_day_shift is sorted
	    	FROM 
	    		public.expected_journeys ej  -- expected_journeys
	    	WHERE 
	    		ej.date_of_journey = date_trunc('day', start_time) 
	        AND 
	        	ej.expected_journey_start < end_time
	        AND 
	        	case 
					when ej.expected_journey_end < ej.expected_journey_start
					then ej.expected_journey_end + interval '1 day'
					else ej.expected_journey_end
				end > start_time; -- todo case can be removed when departure_day_shift is sorted
				
		--
		-- create temp table with stats for avl pings on expected journeys
		--

		RAISE NOTICE 'Creating feedmon_temp_valid_avl for start time = %, End time = %', start_time, end_time;
	
		drop table if exists feedmon_temp_valid_avl;
	
	   	create temporary table feedmon_temp_valid_avl as 
		   	select
		   		s.group_id,
		   		s.recorded_at_time
			from
				"SiriVMPositions" s
			where
				s.date_of_journey = date_trunc('day', start_time)  
			and 
				s.group_id in (select distinct group_id from feedmon_temp_expected_journeys)
			and 
				s.recorded_at_time >= start_time
			and 
				s.recorded_at_time < end_time;
			
		--
		-- create temp table with minute-by-minute rollup of expected vs actual journeys seen
		--
			
		RAISE NOTICE 'Creating feedmon_temp_minute_rollup for start time = %, End time = %', start_time, end_time;
			
		drop table if exists feedmon_temp_minute_rollup;
			
		create temporary table feedmon_temp_minute_rollup as
		with grouped_by_group as (
		select
			gs.minute_series,
			fej.operator_noc,
			fej.group_id,
			count(avl.recorded_at_time) as avl_records
		from	
			generate_series(start_time, end_time - INTERVAL '1 minute', INTERVAL '1 minute') as gs(minute_series)
		inner join
			feedmon_temp_expected_journeys fej
			on fej.expected_journey_start <= gs.minute_series
			and fej.expected_journey_end >= gs.minute_series + INTERVAL '1 minute'
		left join 
			feedmon_temp_valid_avl avl
			on avl.group_id = fej.group_id
			and avl.recorded_at_time >= gs.minute_series
			and avl.recorded_at_time < gs.minute_series + INTERVAL '1 minute'
		group by
			gs.minute_series,
			fej.operator_noc,
			fej.group_id
		)
		select
			date_trunc('day', minute_series)::date as date_of_journey,
			minute_series,
			operator_noc,
			count(*) as expected_distinct_group_id,
			sum(case when avl_records > 0 then 1 else 0 end) as actual_distinct_group_id,
			sum(avl_records) as actual_live_positions_per_minute
		from grouped_by_group
		group by 
			date_trunc('day', minute_series)::date,
			minute_series,
			operator_noc;
		
        --
        -- Create dated partition for minute summaries
        --
        
        RAISE NOTICE 'Creating partition of feed_monitor_minute_summary for date % if needed', date_trunc('day', start_time)::date;
        
        
        execute format(
            'CREATE TABLE if not exists public.%I partition of public.%I FOR VALUES FROM (%L) TO (%L)',
            concat( 'feed_monitor_minute_summary', '_p', to_char(start_time, 'YYYY_MM_DD')),
            'feed_monitor_minute_summary',
            date_trunc('day', start_time)::date,
            date_trunc('day', start_time)::date + interval '1' day
        );
        
        execute format('
            ALTER TABLE public.%I OWNER to abods_rw',
            concat( 'feed_monitor_minute_summary', '_p', to_char(start_time, 'YYYY_MM_DD'))
        );

        --
        -- Delete from dated partition for minute summaries
        --
       
        RAISE NOTICE 'Deleting existing records from % to % from %', 
       	start_time, 
       	end_time,
       	concat( 'feed_monitor_minute_summary', '_p', to_char(start_time, 'YYYY_MM_DD'));
       
        execute format ('
            DELETE FROM public.%I
            WHERE
                received_interval >= %L
            AND
                received_interval < %L
            ',
            concat( 'feed_monitor_minute_summary', '_p', to_char(start_time, 'YYYY_MM_DD')),
            start_time,
            end_time
        );
       
        --
        -- Add to dated partition for minute summaries
        --
       
       	RAISE NOTICE 'Inserting records from feedmon_temp_minute_rollup to %',
       	concat( 'feed_monitor_minute_summary', '_p', to_char(start_time, 'YYYY_MM_DD'));

        execute format ('
            INSERT INTO public.%I (
                date_of_journey,
                operator_noc,
                received_interval,
                expected,
                actual,
                live_locations
            )
            select
				date_of_journey,
				operator_noc,
				minute_series,
				expected_distinct_group_id,
				actual_distinct_group_id,
				actual_live_positions_per_minute			 
			from feedmon_temp_minute_rollup
            ',
            concat( 'feed_monitor_minute_summary', '_p', to_char(start_time, 'YYYY_MM_DD'))
        );
       
       --
       -- Check if the hour we're processing is in the last 24 hours
       -- To determine if an hourly rollup is required
       --
       
       if start_time >= hourly_rollup_period_start
       and start_time < hourly_rollup_period_end
       then
       	RAISE NOTICE 'Start time % is in last 24 hours, updating hourly rollup table',
       	start_time;       		
       		
       		--
       		-- Create and insert rollup for whole hour
       		-- 
       
       		RAISE NOTICE 'Creating feedmon_temp_hour_rollup for start time = %, End time = %', start_time, end_time;
       
			drop table if exists feedmon_temp_hour_rollup;
				
			create temporary table feedmon_temp_hour_rollup as
				with distinct_groups as (
					select distinct operator_noc, group_id 
					from feedmon_temp_expected_journeys
				),
				group_counts as (
				select
					fej.operator_noc,
					fej.group_id,
					count(avl.recorded_at_time) as avl_records
				from 
					 distinct_groups fej
				left join feedmon_temp_valid_avl avl
				on avl.group_id = fej.group_id
				group by 	
					fej.operator_noc,
					fej.group_id
				)
				select 
					operator_noc,
					count(*) as expected_distinct_group_id,
					sum(case when avl_records > 0 then 1 else 0 end) as actual_distinct_group_id
				from group_counts
				group by operator_noc
				;
			
			--
       		-- Delete records for the calculated hour
       		-- 
			
			RAISE NOTICE 'Deleting hourly records from feed_monitor_hourly_summary for start time = %, End time = %',
			start_time, end_time;
			
			delete from public.feed_monitor_hourly_summary 
			where received_interval = date_trunc('hour', start_time);
		
			--
       		-- Delete records older than 24h
       		-- 
			
			RAISE NOTICE 'Deleting hourly records from feed_monitor_hourly_summary where time < %',
			hourly_rollup_period_start;
			
			delete from public.feed_monitor_hourly_summary 
			where received_interval < date_trunc('hour', hourly_rollup_period_start);
			
			--
       		-- Insert records for calculated hour
       		-- 
		
	       	RAISE NOTICE 'Inserting records from feedmon_temp_hour_rollup to feed_monitor_hourly_summary';
		
			insert into public.feed_monitor_hourly_summary (
				operator_noc,
				received_interval,
				expected,
				actual
			)
			select 
				operator_noc,
				date_trunc('hour', start_time),
				expected_distinct_group_id,
				actual_distinct_group_id
			from feedmon_temp_hour_rollup;
			
       end if;

	end loop;
		
end; 
$procedure$
;


alter procedure public.generate_feed_monitoring_data owner to abods_rw;

CREATE OR REPLACE PROCEDURE public.generate_feed_monitor_summary(
	IN start_point timestamptz DEFAULT (date_trunc('hour', now()) - interval '1 hour')
)
 LANGUAGE plpgsql
AS $procedure$
declare
	start_hour TIMESTAMPTZ := date_trunc('hour', start_point);
    end_hour TIMESTAMPTZ := start_hour + interval '1 hour';
	consecutive_missing INT := 15;
begin
	raise notice 'Generating hourly feed monitoring summary for % to %',
	start_hour,
	end_hour;

	--
	-- Create a summary of all expected vs actual for the hour, calculating outages
	--

	drop table if exists temp_generate_feed_monitor_summary_all;

	create temporary table temp_generate_feed_monitor_summary_all as
	with get_outages as ( -- add in outages based on no observed avl
		select 
			operator_noc,
			received_interval,
			expected,
			actual,
			count(*) over (partition by operator_noc) as minutes_with_expected,
			live_locations,
			case
				when actual = 0
				then true
			else 
				false
			end as is_outage,
			case
				when (lag(actual) over (partition by operator_noc order by received_interval asc)) = 0
				then true
			else 
				false 
			end as previous_is_outage
		from public.feed_monitor_minute_summary
		where date_of_journey = date_trunc('day', start_hour)::date 
		and received_interval >= start_hour
		and received_interval < end_hour
	),
	outage_changes as ( -- determine if outage status has changed between current and last
		select
			*,
			case when is_outage <> previous_is_outage
			then 1 else 0
			end as is_new_group
		from get_outages
	),
	outage_groups as ( -- sum up new group headings to group by contiguous outages
		select *,
		sum(is_new_group) over (partition by operator_noc order by received_interval asc) + 1 as outage_group
		from outage_changes
	),
	outage_lengths as ( -- get outage lengths 
		select
		operator_noc,
		received_interval,
		expected,
		actual,
		minutes_with_expected,
		live_locations,
		is_outage,
		case when is_outage
			then outage_group
			else null
		end as outage_group,
		case when is_outage
			then count(*) over outages
			else null
		end as outage_group_length,
		case when is_outage 
			then case
				when first_value(received_interval) over outages = first_value(received_interval) over nocs
				then date_trunc('hour', first_value(received_interval) over outages)
				else first_value(received_interval) over outages
			end
			else null 
		end as outage_start,
		case when is_outage 
			then case
				when last_value(received_interval) over outages = last_value(received_interval) over nocs
				then date_trunc('hour', first_value(received_interval) over outages) + interval '1 hour'
				else last_value(received_interval) over outages + interval '1 minute'
			end
			else null 
		end as outage_end,
		case when is_outage
			then
			case 
				when  first_value(received_interval) over outages = first_value(received_interval) over nocs
				and last_value(received_interval) over outages = last_value(received_interval) over nocs
				then true
				else false 
			end
			else null
		end as is_total_outage,
		case when is_outage
			then
			case 
				when last_value(received_interval) over outages = last_value(received_interval) over nocs
				and count(*) over outages >= consecutive_missing
				then true
				else false 
			end
			else null
		end as is_unavailable
		from outage_groups
		window outages as (partition by operator_noc, outage_group),
		nocs as (partition by operator_noc)
	)
	select 
		*
	from outage_lengths;

	--
	-- Create availabilities for the last 24h for all the expected nocs this hour
	--

	drop table if exists temp_generate_feed_monitor_summary_update_frequencies;

	create temporary table temp_generate_feed_monitor_summary_update_frequencies as
	select -- calculate update frequencies for last 24h if available
		operator_noc,
		case when sum(live_locations) = 0
			then null
		when sum(live_locations) is null
			then null
		else
			round(
				(
					sum(actual::numeric) / sum(live_locations)
				)
				*60,
				0
			)
		end as update_frequency,
		sum(case when actual > 0 then 1 else 0 end)::numeric / sum(case when expected > 0 then 1 else 0 end)::numeric as availability
	from public.feed_monitor_minute_summary
	where (
		date_of_journey= date_trunc('day', start_hour)::date
		or 
		date_of_journey= date_trunc('day', start_hour)::date - interval '1 day'
	)
	and received_interval >= end_hour - interval '1 day'
	and received_interval < end_hour
	and operator_noc in (select distinct operator_noc from temp_generate_feed_monitor_summary_all)
	group by operator_noc;

	--
	-- Create a summary grouped by noc with latest outage and comparators from current summary
	--
	
	drop table if exists temp_generate_feed_monitor_summary_by_noc;

	create temporary table temp_generate_feed_monitor_summary_by_noc as 
	with outage_summary as ( -- generate summary of outages
	select 
		operator_noc,
		outage_group,
		max(outage_group) over (partition by operator_noc) as max_outage_group,
		outage_group_length,
		outage_start,
		outage_end,
		is_total_outage,
		is_unavailable
	from temp_generate_feed_monitor_summary_all
	where is_outage
	and outage_group_length >= consecutive_missing -- filter on configured minimum consecutive missing
	),
	last_outages as ( --calculate when the last outage of the hour was created
	select
		operator_noc,
		outage_group_length,
		outage_start,
		outage_end,
		is_total_outage,
		is_unavailable
	from outage_summary
	where outage_group=max_outage_group
	group by 
		operator_noc,
		outage_group_length,
		outage_group,
		outage_group_length,
		outage_start,
		outage_end,
		is_total_outage,
		is_unavailable
	order by operator_noc, outage_group
	),
	minimum_expected_filter as (
		select distinct operator_noc
		from temp_generate_feed_monitor_summary_all
		where minutes_with_expected >= consecutive_missing 
	)
	select -- aggregate distinct operators with outages update frequencies and full join with existing records to ensure all data available
		mef.operator_noc,
		lo.outage_group_length as outage_length,
		lo.outage_start,
		lo.outage_end-lo.outage_start as outage_length_time,
		lo.is_total_outage,
		lo.is_unavailable,
		uf.update_frequency,
		uf.availability,
		fms.last_outage as previous_last_outage,
		fms.unavailable_since as previous_unavailable_since,
		fms.update_frequency as previous_update_frequency,
		fms.availability as previous_availabiliy
	from minimum_expected_filter mef
	left join last_outages lo
	on mef.operator_noc=lo.operator_noc
	left join temp_generate_feed_monitor_summary_update_frequencies uf 
	on mef.operator_noc = uf.operator_noc
	left join public.feed_monitor_summary fms
	on  mef.operator_noc = fms.operator_noc;

	--
	-- Create update values to upsert into the feed monitoring summary
	--

	drop table if exists temp_generate_feed_monitor_new_values;

	create temporary table temp_generate_feed_monitor_new_values as 
	select
	operator_noc,
	update_frequency,
	case 
		when availability is null then 0
		else availability
	end as availability,
	case
		when is_unavailable = false then null -- if its available then unset unavailable since
		when is_unavailable is null then null -- if its available then unset unavailable since
		when is_unavailable = true
		then
		case
			when is_total_outage = true
			then case
				when previous_unavailable_since is not null
					then previous_unavailable_since -- if unavailable and total outage and there's a previous unavailable set here
				else start_hour -- if unavailable and total outage and there's no previous unavailable set to star of calculated hour
			end
			else outage_start  -- if unavailable and not total outage then the start of the last outage
		end
	end as unavailable_since,
	case 
		when is_unavailable = false or is_unavailable is null then 
		case
			when outage_start is not null then outage_start -- if available and there's a last outage this hour then last outage
			else 
			case
				when previous_unavailable_since is not null
				then previous_unavailable_since -- if available and was previously unavailable then time of previous outage
				else previous_last_outage -- or whatever previous last outage was
			end
		end	
	end as last_outage
	from temp_generate_feed_monitor_summary_by_noc
	;


	insert into public.feed_monitor_summary (
		operator_noc,
		update_frequency,
		availability,
		unavailable_since,
		last_outage
	)
	select 
		operator_noc,
		update_frequency,
		availability,
		unavailable_since,
		last_outage
	from temp_generate_feed_monitor_new_values
	on conflict (operator_noc) do update set (
		update_frequency,
		availability,
		unavailable_since,
		last_outage
	) = (
		EXCLUDED.update_frequency,
		EXCLUDED.availability,
		EXCLUDED.unavailable_since,
		EXCLUDED.last_outage	
	)
	;

end;
$procedure$
;

alter procedure public.generate_feed_monitor_summary owner to abods_rw;

select cron.schedule('update feed stats', '5 * * * *',  $$call public.generate_feed_monitoring_data();call public.generate_feed_monitor_summary();$$);

CREATE OR REPLACE PROCEDURE public.generate_feed_monitoring_daily_summary (
	IN start_point timestamptz DEFAULT (date_trunc('day', now()) - interval '1 day')
)
 LANGUAGE plpgsql
AS $procedure$
declare
    journey_date TIMESTAMPTZ := date_trunc('day', start_point)::date;
begin

	drop table if exists feedmon_temp_day_summary;

	create temporary table feedmon_temp_day_summary as
	select 
		date_of_journey,
		operator_noc,
		case when sum(live_locations) = 0
			then null
		when sum(live_locations) is null
			then null
		else
			round(
				(
					sum(actual::numeric) / sum(live_locations)
				)
				*60,
				0
			)
		end as update_frequency,
		sum(case when actual > 0 then 1 else 0 end)::numeric / sum(case when expected > 0 then 1 else 0 end)::numeric as availability
	from public.feed_monitor_minute_summary
	where date_of_journey= journey_date
	group by date_of_journey, operator_noc;

	delete from public.feed_monitor_daily_summary
	where date_of_journey = journey_date;

	insert into public.feed_monitor_daily_summary (
		date_of_journey,
		operator_noc,
		update_frequency,
		availability
	)
	select 
		date_of_journey,
		operator_noc,
		update_frequency,
		availability
	from feedmon_temp_day_summary;

	delete from public.feed_monitor_daily_summary
	where date_of_journey < current_date - interval '3 month';
	
end;
$procedure$
;

alter procedure public.generate_feed_monitoring_daily_summary owner to abods_rw;

select cron.schedule('update feed hourly stats', '15 1 * * *',  $$call public.generate_feed_monitoring_daily_summary();$$);