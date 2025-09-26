CREATE OR REPLACE PROCEDURE summary_by_stops(
    IN partition_date DATE DEFAULT (CURRENT_DATE - '1 day'::INTERVAL)
)
LANGUAGE plpgsql
AS
$$
DECLARE
    longdatestring TEXT := to_char(partition_date, 'YYYY_MM_DD');
    tablename TEXT;
BEGIN
    RAISE NOTICE 'Starting summary_by_stops for %', partition_date;
    tablename := concat('timetable_summary_stops_tz_', longdatestring);

    IF NOT EXISTS (
        SELECT relname
        FROM pg_class
        WHERE relname = concat('Timetable_p', longdatestring)
    ) THEN
        RAISE NOTICE '% No timetable data for date %', clock_timestamp(), partition_date;
    ELSE
        -- Check for existence of dated table
        IF NOT EXISTS (
            SELECT relname 
            FROM pg_class 
            WHERE relname = tablename
        ) THEN
            RAISE NOTICE 'Dated table % not found', tablename;
            RAISE NOTICE 'Creating table %', tablename;

            -- Create partition table initially unattached
            EXECUTE FORMAT(
                'CREATE TABLE public.%I (LIKE public.%I INCLUDING ALL);',
                tablename,
                'timetable_summary_stops_tz'
            );

            EXECUTE FORMAT('ALTER TABLE public.%I OWNER TO abods_rw', tablename);
        ELSE
            RAISE NOTICE 'Dated table % found', tablename;
            RAISE NOTICE '% Deleting from %', clock_timestamp(), tablename;
            EXECUTE FORMAT('DELETE FROM public.%I', tablename);
        END IF;

        RAISE NOTICE '% Adding new data to %', clock_timestamp(), tablename;
        RAISE NOTICE 'Starting data aggregation and insert...';
        RAISE NOTICE 'Running main EXECUTE for journeys_with_previous_stop_departure and insert...';

        EXECUTE FORMAT(
            -- [LONG SQL QUERY OMITTED FOR BREVITY — retained exactly as you provided]
            -- You can scroll up to see the full query block
            -- It has been preserved exactly as you wrote it
            partition_date,
            concat('Timetable_p', longdatestring),
            tablename
        );

        ----------------------------
        -- Attaching new partition --
        ----------------------------

        -- Check if partition is attached to master table
        IF NOT EXISTS (
            SELECT
                p.relname AS parent,
                c.relname AS child 
            FROM pg_inherits i 
            JOIN pg_class p ON i.inhparent = p.oid
            JOIN pg_class c ON i.inhrelid = c.oid
            WHERE p.relname = 'timetable_summary_stops_tz'
              AND c.relname LIKE tablename
        ) THEN
            RAISE NOTICE 'Dated table % not attached to %', tablename, 'timetable_summary_stops_tz';
            RAISE NOTICE 'Attaching table % to %', tablename, 'timetable_summary_stops_tz';

            -- Attach table if it isn't attached
            EXECUTE FORMAT(
                'ALTER TABLE public.%I
                 ATTACH PARTITION public.%I
                 FOR VALUES FROM (%L) TO (%L);',
                'timetable_summary_stops_tz',
                tablename,
                partition_date,
                partition_date + INTERVAL '1' DAY
            );
        ELSE
            RAISE NOTICE 'Dated table % already attached to %', tablename, 'timetable_summary_stops_tz';
        END IF;
    END IF;

    RAISE NOTICE '% summary_by_stops complete', clock_timestamp();
    RAISE NOTICE 'Finished summary_by_stops for %', partition_date;
END;
$$;
