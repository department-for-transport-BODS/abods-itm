SELECT cron.schedule(
               'Update headway & SiriVMposition id',
               '00 01 * * *',
               $$call public.populate_headway(now()::date - 1);call public.incomplete_data_load(now()::date - 1);$$
       );
SELECT cron.unschedule('create_partition_summary_service');
