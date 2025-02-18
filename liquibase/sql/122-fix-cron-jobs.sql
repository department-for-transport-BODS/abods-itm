SELECT cron.schedule(
               'Update headway & SiriVMposition id',
               '00 01 * * *',
               $$call public.populate_headway(now()::date - 1);call public.incomplete_data_load(now()::date - 1);$$
       );
SELECT cron.unschedule('create_partition_summary_service');
SELECT cron.unschedule('create_partition_operators_if_not_exists');

-- redoing jobs that already exist with no jobname. To make things easier, existing one will be removed manually on deploy
SELECT cron.schedule(
               'partman.run_maintenance_proc',
               '15 23 * * *',
               $$CALL partman.run_maintenance_proc()$$
       );
SELECT cron.schedule(
               'partman.partition_data_proc',
               '00 22 * * *',
               $$CALL partman.partition_data_proc('public.SiriVMPositions')$$
       );
