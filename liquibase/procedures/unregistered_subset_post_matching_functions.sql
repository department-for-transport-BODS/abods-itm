create or replace procedure unregistered_subset_post_matching_functions(IN partition_date date DEFAULT (CURRENT_DATE - '1 day'::interval))
    language plpgsql
as
$$
DECLARE
BEGIN
    RAISE NOTICE '% Running unregistered_subset functions %', clock_timestamp(), partition_date::TEXT;
   
   	call generate_expected_tables_unregistered_subset(partition_date::date);
   
    call populate_headway_unregistered_subset(partition_date::date);
   
    call incomplete_data_load_unregistered_subset(partition_date::date);
   
    call summary_by_stops_unregistered_subset(partition_date::date);
   
    call summary_by_services_unregistered_subset(partition_date::date);

   	call summary_by_operators(partition_date::date);
   
    call frequent_summary_services_unregistered_subset(partition_date::date);
   

    RAISE NOTICE '% Completed unregistered_subset functions for date %', clock_timestamp(), partition_date::TEXT;
END;
$$
;

alter procedure unregistered_subset_post_matching_functions owner to abods_proxy_rw;
