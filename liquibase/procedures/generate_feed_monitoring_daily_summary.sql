create or replace procedure generate_feed_monitoring_daily_summary(IN start_point timestamp with time zone DEFAULT (date_trunc('day'::text, now()) - '1 day'::interval))
    language plpgsql
as
$$
declare
    journey_date TIMESTAMPTZ := date_trunc('day', start_point)::date;
begin

    drop table if exists feedmon_temp_day_summary;

    create temporary table feedmon_temp_day_summary as
    select date_of_journey,
           operator_noc,
           case
               when sum(live_locations) = 0
                   then null
               when sum(live_locations) is null
                   then null
               else
                   round(
                           (
                               sum(actual::numeric) / sum(live_locations)
                               )
                               * 60,
                           0
                   )
               end                                                as update_frequency,
           sum(case when actual > 0 then 1 else 0 end)::numeric /
           sum(case when expected > 0 then 1 else 0 end)::numeric as availability
    from public.feed_monitor_minute_summary
    where date_of_journey = journey_date
    group by date_of_journey, operator_noc;

    delete
    from public.feed_monitor_daily_summary
    where date_of_journey = journey_date;

    insert into public.feed_monitor_daily_summary (date_of_journey,
                                                   operator_noc,
                                                   update_frequency,
                                                   availability)
    select date_of_journey,
           operator_noc,
           update_frequency,
           availability
    from feedmon_temp_day_summary;

    delete
    from public.feed_monitor_daily_summary
    where date_of_journey < current_date - interval '3 month';

end;
$$;
