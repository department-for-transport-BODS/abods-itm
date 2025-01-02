create or replace procedure generate_feed_monitoring_data(IN start_point timestamp with time zone DEFAULT (date_trunc('hour'::text, now()) - '01:00:00'::interval),
                                                          IN whole_day boolean DEFAULT false)
    language plpgsql
as
$$
declare
    start_hour                 TIMESTAMPTZ;
    end_hour                   TIMESTAMPTZ;
    start_time                 TIMESTAMPTZ;
    end_time                   TIMESTAMPTZ;
    hourly_rollup_period_start timestamptz := date_trunc('hour', current_timestamp) - interval '24 hours';
    hourly_rollup_period_end   timestamptz := date_trunc('hour', current_timestamp);
    f                          RECORD;
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

    for f in select generate_series(start_hour, end_hour - interval '1 minute', INTERVAL '1 hour')
        loop
            start_time := f;
            end_time := start_time + interval '1 hour';

            RAISE NOTICE 'Getting expected journeys for start time = %, End time = %', start_time, end_time;

            --
            -- create temp table with stats for expected journeys
            --

            RAISE NOTICE 'Creating feedmon_temp_expected_journeys for start time = %, End time = %', start_time, end_time;

            drop table if exists feedmon_temp_expected_journeys;

            create temporary table feedmon_temp_expected_journeys as
            select DISTINCT ej.operator_noc,
                            ej.group_id,
                            ej.expected_journey_start,
                            case
                                when ej.expected_journey_end < ej.expected_journey_start
                                    then ej.expected_journey_end + interval '1 day'
                                else ej.expected_journey_end
                                end as expected_journey_end -- todo case can be removed when departure_day_shift is sorted
            FROM public.expected_journeys ej -- expected_journeys
            WHERE ej.date_of_journey = date_trunc('day', start_time)
              AND ej.expected_journey_start < end_time
              AND case
                      when ej.expected_journey_end < ej.expected_journey_start
                          then ej.expected_journey_end + interval '1 day'
                      else ej.expected_journey_end
                      end > start_time;
            -- todo case can be removed when departure_day_shift is sorted

            --
            -- create temp table with stats for avl pings on expected journeys
            --

            RAISE NOTICE 'Creating feedmon_temp_valid_avl for start time = %, End time = %', start_time, end_time;

            drop table if exists feedmon_temp_valid_avl;

            create temporary table feedmon_temp_valid_avl as
            select s.group_id,
                   s.recorded_at_time
            from "SiriVMPositions" s
            where s.date_of_journey = date_trunc('day', start_time)
              and s.group_id in (select distinct group_id from feedmon_temp_expected_journeys)
              and s.recorded_at_time >= start_time
              and s.recorded_at_time < end_time;

            --
            -- create temp table with minute-by-minute rollup of expected vs actual journeys seen
            --

            RAISE NOTICE 'Creating feedmon_temp_minute_rollup for start time = %, End time = %', start_time, end_time;

            drop table if exists feedmon_temp_minute_rollup;

            create temporary table feedmon_temp_minute_rollup as
            with grouped_by_group as (select gs.minute_series,
                                             fej.operator_noc,
                                             fej.group_id,
                                             count(avl.recorded_at_time) as avl_records
                                      from generate_series(start_time, end_time - INTERVAL '1 minute',
                                                           INTERVAL '1 minute') as gs(minute_series)
                                               inner join
                                           feedmon_temp_expected_journeys fej
                                           on fej.expected_journey_start <= gs.minute_series
                                               and fej.expected_journey_end >= gs.minute_series + INTERVAL '1 minute'
                                               left join
                                           feedmon_temp_valid_avl avl
                                           on avl.group_id = fej.group_id
                                               and avl.recorded_at_time >= gs.minute_series
                                               and avl.recorded_at_time < gs.minute_series + INTERVAL '1 minute'
                                      group by gs.minute_series,
                                               fej.operator_noc,
                                               fej.group_id)
            select date_trunc('day', minute_series)::date           as date_of_journey,
                   minute_series,
                   operator_noc,
                   count(*)                                         as expected_distinct_group_id,
                   sum(case when avl_records > 0 then 1 else 0 end) as actual_distinct_group_id,
                   sum(avl_records)                                 as actual_live_positions_per_minute
            from grouped_by_group
            group by date_trunc('day', minute_series)::date,
                     minute_series,
                     operator_noc;

            --
            -- Create dated partition for minute summaries
            --

            RAISE NOTICE 'Creating partition of feed_monitor_minute_summary for date % if needed', date_trunc('day', start_time)::date;


            execute format(
                    'CREATE TABLE if not exists public.%I partition of public.%I FOR VALUES FROM (%L) TO (%L)',
                    concat('feed_monitor_minute_summary', '_p', to_char(start_time, 'YYYY_MM_DD')),
                    'feed_monitor_minute_summary',
                    date_trunc('day', start_time)::date,
                    date_trunc('day', start_time)::date + interval '1' day
                    );

            execute format('
            ALTER TABLE public.%I OWNER to abods_rw',
                           concat('feed_monitor_minute_summary', '_p', to_char(start_time, 'YYYY_MM_DD'))
                    );

            --
            -- Delete from dated partition for minute summaries
            --

            RAISE NOTICE 'Deleting existing records from % to % from %',
                start_time,
                end_time,
                concat('feed_monitor_minute_summary', '_p', to_char(start_time, 'YYYY_MM_DD'));

            execute format('
            DELETE FROM public.%I
            WHERE
                received_interval >= %L
            AND
                received_interval < %L
            ',
                           concat('feed_monitor_minute_summary', '_p', to_char(start_time, 'YYYY_MM_DD')),
                           start_time,
                           end_time
                    );

            --
            -- Add to dated partition for minute summaries
            --

            RAISE NOTICE 'Inserting records from feedmon_temp_minute_rollup to %',
                concat('feed_monitor_minute_summary', '_p', to_char(start_time, 'YYYY_MM_DD'));

            execute format('
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
                           concat('feed_monitor_minute_summary', '_p', to_char(start_time, 'YYYY_MM_DD'))
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
                with distinct_groups as (select distinct operator_noc, group_id
                                         from feedmon_temp_expected_journeys),
                     group_counts as (select fej.operator_noc,
                                             fej.group_id,
                                             count(avl.recorded_at_time) as avl_records
                                      from distinct_groups fej
                                               left join feedmon_temp_valid_avl avl
                                                         on avl.group_id = fej.group_id
                                      group by fej.operator_noc,
                                               fej.group_id)
                select operator_noc,
                       count(*)                                         as expected_distinct_group_id,
                       sum(case when avl_records > 0 then 1 else 0 end) as actual_distinct_group_id
                from group_counts
                group by operator_noc;

                --
                -- Delete records for the calculated hour
                --

                RAISE NOTICE 'Deleting hourly records from feed_monitor_hourly_summary for start time = %, End time = %',
                    start_time, end_time;

                delete
                from public.feed_monitor_hourly_summary
                where received_interval = date_trunc('hour', start_time);

                --
                -- Delete records older than 24h
                --

                RAISE NOTICE 'Deleting hourly records from feed_monitor_hourly_summary where time < %',
                    hourly_rollup_period_start;

                delete
                from public.feed_monitor_hourly_summary
                where received_interval < date_trunc('hour', hourly_rollup_period_start);

                --
                -- Insert records for calculated hour
                --

                RAISE NOTICE 'Inserting records from feedmon_temp_hour_rollup to feed_monitor_hourly_summary';

                insert into public.feed_monitor_hourly_summary (operator_noc,
                                                                received_interval,
                                                                expected,
                                                                actual)
                select operator_noc,
                       date_trunc('hour', start_time),
                       expected_distinct_group_id,
                       actual_distinct_group_id
                from feedmon_temp_hour_rollup;

            end if;

        end loop;

end;
$$;

alter procedure generate_feed_monitoring_data owner to abods_proxy_rw;
