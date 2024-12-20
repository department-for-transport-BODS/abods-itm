create or replace procedure update_avl_line_level_monitoring(IN partition_date date DEFAULT (CURRENT_DATE - '1 day'::interval))
    language plpgsql
as
$$
begin
    insert into avl_line_level_monitoring
    select operator_ref,
           line_name,
           max(recorded_at_time)
    from public."SiriVMPositions"
    where date_of_journey = partition_date
    group by operator_ref, line_name
    on conflict (operator_noc, line_name)
        do update
        set last_recorded_at_time = EXCLUDED.last_recorded_at_time;

end;
$$;
