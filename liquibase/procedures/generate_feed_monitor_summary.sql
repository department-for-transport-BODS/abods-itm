create or replace procedure generate_feed_monitor_summary(IN start_point timestamp with time zone DEFAULT (date_trunc('hour'::text, now()) - '01:00:00'::interval))
    language plpgsql
as
$$
declare
    start_hour          TIMESTAMPTZ := date_trunc('hour', start_point);
    end_hour            TIMESTAMPTZ := start_hour + interval '1 hour';
    consecutive_missing INT         := 15;
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
        select operator_noc,
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
                   end                                   as is_outage,
               case
                   when (lag(actual) over (partition by operator_noc order by received_interval asc)) = 0
                       then true
                   else
                       false
                   end                                   as previous_is_outage
        from public.feed_monitor_minute_summary
        where date_of_journey = date_trunc('day', start_hour)::date
          and received_interval >= start_hour
          and received_interval < end_hour),
         outage_changes as ( -- determine if outage status has changed between current and last
             select *,
                    case
                        when is_outage <> previous_is_outage
                            then 1
                        else 0
                        end as is_new_group
             from get_outages),
         outage_groups as ( -- sum up new group headings to group by contiguous outages
             select *,
                    sum(is_new_group) over (partition by operator_noc order by received_interval asc) +
                    1 as outage_group
             from outage_changes),
         outage_lengths as ( -- get outage lengths
             select operator_noc,
                    received_interval,
                    expected,
                    actual,
                    minutes_with_expected,
                    live_locations,
                    is_outage,
                    case
                        when is_outage
                            then outage_group
                        else null
                        end as outage_group,
                    case
                        when is_outage
                            then count(*) over outages
                        else null
                        end as outage_group_length,
                    case
                        when is_outage
                            then case
                                     when first_value(received_interval) over outages =
                                          first_value(received_interval) over nocs
                                         then date_trunc('hour', first_value(received_interval) over outages)
                                     else first_value(received_interval) over outages
                            end
                        else null
                        end as outage_start,
                    case
                        when is_outage
                            then case
                                     when last_value(received_interval) over outages =
                                          last_value(received_interval) over nocs
                                         then date_trunc('hour', first_value(received_interval) over outages) +
                                              interval '1 hour'
                                     else last_value(received_interval) over outages + interval '1 minute'
                            end
                        else null
                        end as outage_end,
                    case
                        when is_outage
                            then
                            case
                                when first_value(received_interval) over outages =
                                     first_value(received_interval) over nocs
                                    and last_value(received_interval) over outages =
                                        last_value(received_interval) over nocs
                                    then true
                                else false
                                end
                        else null
                        end as is_total_outage,
                    case
                        when is_outage
                            then
                            case
                                when last_value(received_interval) over outages =
                                     last_value(received_interval) over nocs
                                    and count(*) over outages >= consecutive_missing
                                    then true
                                else false
                                end
                        else null
                        end as is_unavailable
             from outage_groups
             window outages as (partition by operator_noc, outage_group),
                    nocs as (partition by operator_noc))
    select *
    from outage_lengths;

    --
    -- Create availabilities for the last 24h for all the expected nocs this hour
    --

    drop table if exists temp_generate_feed_monitor_summary_update_frequencies;

    create temporary table temp_generate_feed_monitor_summary_update_frequencies as
    select -- calculate update frequencies for last 24h if available
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
    where (
        date_of_journey = date_trunc('day', start_hour)::date
            or
        date_of_journey = date_trunc('day', start_hour)::date - interval '1 day'
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
        select operator_noc,
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
             select operator_noc,
                    outage_group_length,
                    outage_start,
                    outage_end,
                    is_total_outage,
                    is_unavailable
             from outage_summary
             where outage_group = max_outage_group
             group by operator_noc,
                      outage_group_length,
                      outage_group,
                      outage_group_length,
                      outage_start,
                      outage_end,
                      is_total_outage,
                      is_unavailable
             order by operator_noc, outage_group),
         minimum_expected_filter as (select distinct operator_noc
                                     from temp_generate_feed_monitor_summary_all
                                     where minutes_with_expected >= consecutive_missing)
    select -- aggregate distinct operators with outages update frequencies and full join with existing records to ensure all data available
           mef.operator_noc,
           lo.outage_group_length          as outage_length,
           lo.outage_start,
           lo.outage_end - lo.outage_start as outage_length_time,
           lo.is_total_outage,
           lo.is_unavailable,
           uf.update_frequency,
           uf.availability,
           fms.last_outage                 as previous_last_outage,
           fms.unavailable_since           as previous_unavailable_since,
           fms.update_frequency            as previous_update_frequency,
           fms.availability                as previous_availabiliy
    from minimum_expected_filter mef
             left join last_outages lo
                       on mef.operator_noc = lo.operator_noc
             left join temp_generate_feed_monitor_summary_update_frequencies uf
                       on mef.operator_noc = uf.operator_noc
             left join public.feed_monitor_summary fms
                       on mef.operator_noc = fms.operator_noc;

    --
    -- Create update values to upsert into the feed monitoring summary
    --

    drop table if exists temp_generate_feed_monitor_new_values;

    create temporary table temp_generate_feed_monitor_new_values as
    select operator_noc,
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
                       else outage_start -- if unavailable and not total outage then the start of the last outage
                       end
               end as unavailable_since,
           case
               when is_unavailable = false or is_unavailable is null then
                   case
                       when outage_start is not null
                           then outage_start -- if available and there's a last outage this hour then last outage
                       else
                           case
                               when previous_unavailable_since is not null
                                   then previous_unavailable_since -- if available and was previously unavailable then time of previous outage
                               else previous_last_outage -- or whatever previous last outage was
                               end
                       end
               end as last_outage
    from temp_generate_feed_monitor_summary_by_noc;


    insert into public.feed_monitor_summary (operator_noc,
                                             update_frequency,
                                             availability,
                                             unavailable_since,
                                             last_outage)
    select operator_noc,
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
        );

end;
$$;
