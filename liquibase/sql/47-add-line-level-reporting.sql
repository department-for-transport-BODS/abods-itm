CREATE TABLE IF NOT EXISTS public.avl_line_level_monitoring (
  operator_noc TEXT NOT NULL,
  line_name TEXT NOT NULL,
  last_recorded_at_time timestamptz NOT NULL,
    PRIMARY KEY (operator_noc, line_name)
);

alter table public.avl_line_level_monitoring
owner to abods_rw;

CREATE OR REPLACE PROCEDURE public.update_avl_line_level_monitoring(
	IN partition_date date 
	default current_date - interval '1 day'
)
 LANGUAGE plpgsql
AS $procedure$
begin
	insert into avl_line_level_monitoring
	select 
		operator_ref,
		line_name,
		max(recorded_at_time)
	from public."SiriVMPositions"
	where date_of_journey = partition_date
	group by operator_ref, line_name
	on conflict (operator_noc, line_name)
	do update 
	set last_recorded_at_time = EXCLUDED.last_recorded_at_time;

end;
$procedure$
;

alter procedure public.update_avl_line_level_monitoring
owner to abods_rw;

select cron.schedule('update avl line level monitoring', '25 1 * * *',  $$call public.update_avl_line_level_monitoring();$$);