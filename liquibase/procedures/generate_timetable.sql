create or replace procedure generate_timetable(IN partition_date date)
    language plpgsql
as
$$

declare
    longdatestring   text := to_char(partition_date, 'YYYY_MM_DD');
    timetable_suffix text := concat('_', longdatestring);
    tablename        text := 'Timetable';

begin

    RAISE NOTICE '% (Re)Creating filtered_files temp table', clock_timestamp();

    execute format('DROP TABLE IF EXISTS public.%I', concat('filtered_files', timetable_suffix));

    IF partition_date > now() THEN
        execute format(
                '
                CREATE TABLE public.%I AS
                SELECT
                  od.dataset_id,
                  a.id AS txcfileattributes_id,
                  a.national_operator_code,
                  a.service_code,
                  a.line_names AS line_name,
                  a.filename,
                  a.revision_number,
                  a.revision_id,
                  a.operating_period_start_date,
                  a.operating_period_end_date
                FROM
                  public.organisation_txcfileattributes a
                  JOIN public.organisation_datasetrevision od
                    ON od.id = a.revision_id
                  INNER JOIN public.organisation_dataset d
                    ON d.live_revision_id = a.revision_id
                WHERE
                      od.is_published IS TRUE
                  AND od.status = ''live''
                  AND d.dataset_type = 1
                ',
                concat('filtered_files', timetable_suffix),
                partition_date,
                partition_date
                );
    ELSE
        execute format(
                '
                CREATE TABLE public.%I AS
                WITH potential_datasets AS (
                  --get list of all potential timetable dataset ids (od2.dataset_type = 1)
                  SELECT
                    od2.id dataset_table_id,
                    od2.dataset_type
                  FROM
                    organisation_dataset od2
                  WHERE
                    od2.dataset_type = 1
                ),
                potential_revisions AS (
                  -- get all potentially live revisions where published before the date we are interested in
                  SELECT
                    (%L)::timestamptz AS query_date,
                    od.*,
                    pd.*
                  FROM
                    organisation_datasetrevision od
                    INNER JOIN potential_datasets pd
                      ON pd.dataset_table_id = od.dataset_id
                  WHERE
                        od.published_at <= (%L)::timestamptz
                    AND od.status IN (
                      ''live'',
                      ''inactive'',
                      ''expired''
                    )
                ),
                inactive_at_date_prequery AS (
                  -- get all potentially live revisions where published before the date we are interested in
                  SELECT
                    *,
                    rank() OVER (
                      PARTITION BY dataset_id
                      ORDER BY
                        id DESC
                    ) AS id_rank
                  FROM
                    potential_revisions
                ),
                inactive_at_date AS (
                  --get all potential revision grouped by dataset_id ranked by highest modified date
                  SELECT
                    DISTINCT dataset_id
                  FROM
                    inactive_at_date_prequery
                  WHERE
                        id_rank = 1
                    AND modified < query_date
                    AND status IN (''inactive'', ''expired'')
                ),
                ranked_revisions AS (
                  -- list dataset ids at latest revision where modified before query date
                  SELECT
                    pr.*,
                    rank() OVER (
                      PARTITION BY pr.dataset_id
                      ORDER BY
                        id DESC
                    ) AS id_rank
                  FROM
                    potential_revisions pr
                    LEFT JOIN inactive_at_date iad
                      ON pr.dataset_id = iad.dataset_id
                  WHERE
                    iad.dataset_id IS NULL
                ),
                highest_revisions AS (
                  -- rank revisions which are not inactive at date by most modified
                  SELECT
                    rr.*
                  FROM
                    ranked_revisions rr
                  WHERE
                    rr.id_rank = 1
                ),
                selected_revisions AS (
                  SELECT
                    DISTINCT id AS revision_id,
                    dataset_id
                  FROM
                    highest_revisions
                )
                SELECT
                  p.dataset_id,
                  a.id AS txcfileattributes_id,
                  a.national_operator_code,
                  a.service_code,
                  a.line_names AS line_name,
                  a.filename,
                  a.revision_number,
                  a.revision_id,
                  a.operating_period_start_date,
                  a.operating_period_end_date
                FROM
                  selected_revisions p
                  LEFT JOIN public.organisation_txcfileattributes a
                    ON p.revision_id = a.revision_id
                WHERE
                  a.id IS NOT NULL
                ',
                concat('filtered_files', timetable_suffix),
                partition_date,
                partition_date
                );
    END IF;

    RAISE NOTICE '% (Re)Creating organisation_timetable temp table', clock_timestamp();

    execute format('DROP TABLE IF EXISTS public.%I', concat('organisation_timetable', timetable_suffix));

    execute format(
            '
            CREATE TABLE public.%I AS
            WITH query_date_dataset_revision AS (
              SELECT
                f.dataset_id,
                f.txcfileattributes_id,
                f.national_operator_code,
                f.service_code,
                f.line_name,
                f.filename,
                f.revision_number,
                f.revision_id,
                f.operating_period_start_date,
                f.operating_period_end_date
              FROM
                public.%I f
              WHERE
                    %L BETWEEN f.operating_period_start_date
                AND COALESCE (
                  f.operating_period_end_date,
                  ''2050-12-31''::date
                )
            ),
            max_file_revision_number AS (
              SELECT
                x.national_operator_code,
                x.service_code,
                max(x.revision_number) AS max_revision_number
              FROM
                query_date_dataset_revision x
              GROUP BY
                x.national_operator_code,
                x.service_code
            ),
            max_start_dates AS (
              SELECT
                x.national_operator_code,
                x.service_code,
                max(x.revision_number) AS max_revision_number
              FROM
                public.%I x
              WHERE
                x.operating_period_end_date < %L
              GROUP BY
                x.national_operator_code,
                x.service_code
            )
            SELECT
              DISTINCT drv.txcfileattributes_id,
              drv.national_operator_code,
              drv.service_code,
              drv.line_name,
              drv.filename,
              drv.revision_id,
              drv.revision_number
            FROM
              (
                SELECT
                  DISTINCT m.txcfileattributes_id,
                  m.national_operator_code,
                  m.service_code,
                  m.line_name,
                  m.filename,
                  m.revision_id,
                  m.revision_number
                FROM
                  query_date_dataset_revision m
                  JOIN max_file_revision_number f
                    ON  m.national_operator_code = f.national_operator_code
                    AND m.service_code = f.service_code
                    AND m.revision_number = f.max_revision_number
              ) drv
              LEFT JOIN max_start_dates s ON
                  drv.national_operator_code = s.national_operator_code
              AND drv.service_code = s.service_code
              AND drv.revision_number < s.max_revision_number
            WHERE
              s.max_revision_number IS NULL
            ORDER BY
              drv.national_operator_code,
              drv.service_code,
              drv.line_name;
	        ',
            concat('organisation_timetable', timetable_suffix),
            concat('filtered_files', timetable_suffix),
            partition_date,
            concat('filtered_files', timetable_suffix),
            partition_date
            );

    RAISE NOTICE '% (Re)Creating filtered_registered_organisation_timetable table', clock_timestamp();

    execute format('DROP TABLE IF EXISTS public.%I', concat('filtered_registered_organisation_timetable', timetable_suffix));

    execute format(
            '
            CREATE TABLE public.%I AS
            SELECT
              *
            FROM
              (
                WITH operator_UZ_group AS (
                  SELECT
                    txcfileattributes_id,
                    national_operator_code,
                    service_code,
                    line_name,
                    filename,
                    revision_id,
                    revision_number,
                    NULL AS otc_service_code,
                    NULL AS registration_status
                  FROM
                    public.%I
                  WHERE
                    service_code like ''UZ%%''
                )
                SELECT
                  ot.txcfileattributes_id,
                  ot.national_operator_code,
                  ot.service_code,
                  ot.line_name,
                  ot.filename,
                  ot.revision_id,
                  ot.revision_number,
                  osn.otc_service_code,
                  osn.registration_status
                FROM
                  public.%I ot
                  JOIN (
                    SELECT
                      os.registration_number,
                      registration_code,
                      concat_ws(
                        '':'',
                        substring(os.registration_number, 1, 9),
                        substring(os.registration_number, 11, 12)
                      ) AS otc_service_code,
                      os.registration_status,
                      os.effective_date
                    FROM
                      bods.otc_service os
                      LEFT JOIN bods.otc_inactiveservice ois
                        ON  os.registration_number = ois.registration_number
                        AND ois.registration_status = ''Registered''
                        AND ois.effective_date = %L::date + 1
                    WHERE
                         os.registration_status = ''Registered''
                      OR os.registration_status = ''''
                      OR os.registration_status = ''New''
                      OR (
                            os.registration_status != ''Registered''
                        AND os.registration_status != ''''
                        AND os.effective_date > %L::date + 1
                      )
                  ) osn ON ot.service_code = osn.otc_service_code
                UNION
                SELECT
                  *
                FROM
                  operator_UZ_group
              );
            ',
            concat('filtered_registered_organisation_timetable', timetable_suffix),
            concat('organisation_timetable', timetable_suffix),
            concat('organisation_timetable', timetable_suffix),
            partition_date,
            partition_date
            );

    RAISE NOTICE '% (Re)Creating timetable_vehiclejourney temp table', clock_timestamp();

    execute format('DROP TABLE IF EXISTS public.%I', concat('timetable_vehiclejourney', timetable_suffix));

    execute format(
            '
            CREATE TABLE public.%I AS
            SELECT
              a.*,
              tv.*,
              %L::date AS date_of_journey,
              ts2.line_name AS exploded_line_name
            FROM
              public.%I a
              JOIN public.transmodel_service ts
                ON  a.revision_id = ts.revision_id
                AND a.txcfileattributes_id = ts.txcfileattributes_id
                AND %L BETWEEN ts.start_date
                AND coalesce(ts.end_date, ''2050-12-31''::date)
              JOIN public.transmodel_service_service_patterns tssp
                ON ts.id = tssp.service_id
              JOIN public.transmodel_servicepattern ts2
                ON tssp.servicepattern_id = ts2.id
              JOIN public.transmodel_vehiclejourney tv
                ON ts2.id = tv.service_pattern_id;
            ',
            concat('timetable_vehiclejourney', timetable_suffix),
            partition_date,
            concat('filtered_registered_organisation_timetable', timetable_suffix),
            partition_date
            );


    RAISE NOTICE '% (Re)Creating timetable_vehiclejourney_workingdays temp table', clock_timestamp();

    execute format('DROP TABLE IF EXISTS public.%I', concat('timetable_vehiclejourney_workingdays', timetable_suffix));

    execute format(
            '
            CREATE TABLE public.%I AS
            SELECT
              tv.*
            FROM
              public.%I tv
              LEFT JOIN (
                SELECT
                  tv.id,
                  (
                    CASE WHEN toe.vehicle_journey_id IS NOT NULL THEN ''yes''
                      ELSE max(
                        CASE WHEN ts.operating_on_working_days IS TRUE
                              AND tsw.serviced_organisation_vehicle_journey_id IS NULL
                          THEN ''no''
                        WHEN ts.operating_on_working_days IS TRUE
                         AND tsw.serviced_organisation_vehicle_journey_id IS NOT NULL
                          THEN ''yes''
                        WHEN ts.operating_on_working_days IS FALSE
                         AND tsw.serviced_organisation_vehicle_journey_id IS NOT NULL
                          THEN ''no''
                          ELSE ''yes''
                        END
                      )
                    END
                  ) AS flag
                FROM
                  public.%I tv
                  LEFT JOIN (
                    SELECT
                      vehicle_journey_id
                    FROM
                      public.transmodel_operatingdatesexceptions
                    WHERE
                      %L::date = operating_date
                  ) toe
                    ON tv.id = toe.vehicle_journey_id
                  JOIN public.transmodel_servicedorganisationvehiclejourney ts
                    ON tv.id = ts.vehicle_journey_id
                  LEFT JOIN (
                    SELECT
                      serviced_organisation_vehicle_journey_id
                    FROM
                      public.transmodel_servicedorganisationworkingdays
                    WHERE
                      %L::date BETWEEN start_date
                      AND end_date
                    GROUP BY
                      serviced_organisation_vehicle_journey_id
                  ) tsw
                    ON ts.id = tsw.serviced_organisation_vehicle_journey_id
                GROUP BY
                  tv.id,
                  toe.vehicle_journey_id
              ) workingday
                ON tv.id = workingday.id
            WHERE
              coalesce(workingday.flag, ''yes'') = ''yes'';
	        ',
            concat('timetable_vehiclejourney_workingdays', timetable_suffix),
            concat('timetable_vehiclejourney', timetable_suffix),
            concat('timetable_vehiclejourney', timetable_suffix),
            partition_date,
            partition_date
            );

    RAISE NOTICE '% (Re)Creating timetable_vehiclejourney_exclusions temp table', clock_timestamp();

    execute format('DROP TABLE IF EXISTS public.%I', concat('timetable_vehiclejourney_exclusions', timetable_suffix));

    execute format(
            '
            CREATE TABLE public.%I AS
            SELECT
              id
            FROM
              (
                SELECT
                  tvw.id,
                  (
                    CASE WHEN toe.vehicle_journey_id IS NOT NULL
                      THEN 1
                    ELSE MAX(
                      CASE WHEN top.day_of_week = trim(to_char(%L::date, ''Day''))
                        THEN 1 -- include
                        ELSE 0 -- exclude
                      END
                    )
                    END
                  ) AS flag
                FROM
                  public.%I tvw
                  LEFT JOIN (
                    SELECT
                      vehicle_journey_id
                    FROM
                      public.transmodel_operatingdatesexceptions
                    WHERE
                      %L::date = operating_date
                  ) toe
                    ON tvw.id = toe.vehicle_journey_id
                  LEFT JOIN public.transmodel_operatingprofile top
                    ON tvw.id = top.vehicle_journey_id
                GROUP BY
                  tvw.id,
                  toe.vehicle_journey_id
              ) oper
            WHERE
              oper.flag = 0;
	        ',
            concat('timetable_vehiclejourney_exclusions', timetable_suffix),
            partition_date,
            concat('timetable_vehiclejourney_workingdays', timetable_suffix),
            partition_date
            );

    RAISE NOTICE '% Inserting into timetable_vehiclejourney_exclusions temp table', clock_timestamp();

    execute format(
            '
            INSERT INTO
              public.%I (id)
            SELECT
              tvw.id
            FROM
              public.%I tvw
              JOIN public.transmodel_nonoperatingdatesexceptions tne
                ON tvw.id = tne.vehicle_journey_id
            WHERE
              tne.non_operating_date = %L::date
            GROUP BY
              1;
	        ',
            concat('timetable_vehiclejourney_exclusions', timetable_suffix),
            concat('timetable_vehiclejourney_workingdays', timetable_suffix),
            partition_date,
            concat('timetable_vehiclejourney_exclusions', timetable_suffix),
            partition_date
            );


    RAISE NOTICE '% (Re)Creating timetable_journey_workingdays_with_exclusions temp table', clock_timestamp();

    execute format('DROP TABLE IF EXISTS public.%I', concat('timetable_journey_workingdays_with_exclusions', timetable_suffix));

    execute format(
            '
            CREATE TABLE public.%I AS
            SELECT
              a.*
            FROM
              public.%I a
              LEFT JOIN public.%I b
                ON a.id = b.id
            WHERE
              b.id IS NULL;
	        ',
            concat('timetable_journey_workingdays_with_exclusions', timetable_suffix),
            concat('timetable_vehiclejourney_workingdays', timetable_suffix),
            concat('timetable_vehiclejourney_exclusions', timetable_suffix)
            );


    RAISE NOTICE '% (Re)Creating timetable_vehiclejourney_servicecode_dupes temp table', clock_timestamp();

    execute format('DROP TABLE IF EXISTS public.%I', concat('timetable_vehiclejourney_servicecode_dupes', timetable_suffix));

    execute format(
            '
            CREATE TABLE public.%I AS
            SELECT
              national_operator_code,
              exploded_line_name AS line_name,
              journey_code
            FROM
              public.%I
            GROUP BY
              national_operator_code,
              exploded_line_name,
              journey_code
            HAVING
              count(DISTINCT service_code) > 1;
            ',
            concat('timetable_vehiclejourney_servicecode_dupes', timetable_suffix),
            concat('timetable_journey_workingdays_with_exclusions', timetable_suffix)
            );

    RAISE NOTICE '% (Re)Creating timetable_vehiclejourney_nodupes temp table', clock_timestamp();

    execute format('DROP TABLE IF EXISTS public.%I', concat('timetable_vehiclejourney_nodupes', timetable_suffix));

    execute format(
            '
            CREATE TABLE public.%I AS
            SELECT
              a.*
            FROM
              public.%I a
              LEFT JOIN public.%I drv
                ON  a.national_operator_code = drv.national_operator_code
                AND a.exploded_line_name = drv.line_name
                AND a.journey_code = drv.journey_code
            WHERE
              drv.journey_code IS NULL;
            ',
            concat('timetable_vehiclejourney_nodupes', timetable_suffix),
            concat('timetable_journey_workingdays_with_exclusions', timetable_suffix),
            concat('timetable_vehiclejourney_servicecode_dupes', timetable_suffix)
            );

    RAISE NOTICE '% (Re)Creating timetable_vj_per_groupid temp table', clock_timestamp();

    execute format('DROP TABLE IF EXISTS public.%I', concat('timetable_vj_per_groupid', timetable_suffix));

    execute format(
            '
            CREATE TABLE public.%I AS
            WITH ranked_directional_journeys AS (
              SELECT
                row_number() OVER w AS rank,
                count(1) OVER w AS window_size,
                national_operator_code AS operator_ref,
                service_code,
                filename,
                exploded_line_name AS line_name,
                journey_code,
                date_of_journey,
                direction,
                tvw.id AS transmodel_vehiclejourney_id,
                tvw.service_pattern_id AS transmodel_servicepattern_id,
                departure_day_shift,
                concat_ws(
                  ''|'',
                  national_operator_code,
                  exploded_line_name,
                  journey_code,
                  date_of_journey
                ) AS group_id
              FROM
                public.%I tvw
              WHERE
                trim(tvw.journey_code) <> '''' WINDOW w AS (
                  PARTITION BY national_operator_code,
                  exploded_line_name,
                  journey_code,
                  date_of_journey,
                  direction
                  ORDER BY
                    id DESC,
                    service_pattern_id DESC RANGE BETWEEN UNBOUNDED PRECEDING
                    AND UNBOUNDED FOLLOWING
                )
            )
            SELECT
              count(1) OVER w2 AS journey_partition_size,
              *
            FROM
              ranked_directional_journeys
            WHERE
              rank = 1 WINDOW w2 AS (
                PARTITION BY operator_ref,
                line_name,
                journey_code,
                date_of_journey RANGE BETWEEN UNBOUNDED PRECEDING
                AND UNBOUNDED FOLLOWING
              )
            ORDER BY
              count(1) OVER w2 DESC,
              operator_ref,
              line_name,
              journey_code;
            ',
            concat('timetable_vj_per_groupid', timetable_suffix),
            concat('timetable_vehiclejourney_nodupes', timetable_suffix)
            );

    RAISE NOTICE '% (Re)Creating timetable_journey temp table', clock_timestamp();

    execute format('DROP TABLE IF EXISTS public.%I', concat('timetable_journey', timetable_suffix));

    execute format(
            '
            CREATE TABLE public.%I AS
            SELECT
              operator_ref,
              service_code,
              line_name,
              filename AS file_name,
              journey_code,
              date_of_journey,
              extract(
                dow
                FROM
                  date_of_journey
              ) AS day_of_week,
              coalesce(stop.naptan_stop_id::text, '''') AS stop_id,
              stop.sequence_number AS stop_index,
              stop.departure_time AS departure_time,
              stop.is_timing_point AS is_timing_point,
              group_id,
              transmodel_vehiclejourney_id,
              transmodel_servicepattern_id,
              stop.atco_code,
              direction,
              departure_day_shift
            FROM
              public.%I tvw
              JOIN public.transmodel_servicepatternstop stop
                ON tvw.transmodel_vehiclejourney_id = stop.vehicle_journey_id
	        ',
            concat('timetable_journey', timetable_suffix),
            concat('timetable_vj_per_groupid', timetable_suffix)
            );

    RAISE NOTICE '% (Re)Creating timetable_stop temp table', clock_timestamp();

    execute format('DROP TABLE IF EXISTS public.%I', concat('timetable_stop', timetable_suffix));

    execute format(
            '
            CREATE TABLE public.%I AS
            SELECT
              operator_ref,
              line_name,
              journey_code,
              date_of_journey AS date_of_journey,
              departure_time,
              stop_id,
              ST_Y(b.location)::real lt,
              ST_X(b.location)::real AS lon,
              common_name AS stopname,
              a.stop_index,
              b.common_name AS stop_name,
              a.is_timing_point,
              b.locality_id,
              service_code,
              file_name AS filename,
              day_of_week,
              stop_type,
              group_id,
              a.atco_code,
              row_number() over(
                PARTITION BY operator_ref,
                line_name,
                journey_code,
                date_of_journey,
                stop_id,
                stop_index
                ORDER BY
                  file_name
              ) AS rk,
              transmodel_servicepattern_id,
              transmodel_vehiclejourney_id AS vehiclejourney_id,
              b.admin_area_id,
              direction,
              departure_day_shift,
              -- We use these in the next query to help calculate the right date to put in the expected_departure_time
              -- because the raw data only sets departure_day_shift to true if the first stop departure is after midnight
              FIRST_VALUE(departure_time) OVER w AS first_departure,
              LAST_VALUE(departure_time) OVER w AS last_departure
            FROM
              public.%I a
              JOIN public.naptan_stoppoint b
                ON a.stop_id = b.id::text
              WINDOW w AS (
                PARTITION BY transmodel_vehiclejourney_id
                ORDER BY
                  stop_index RANGE BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
              );
	        ',
            concat('timetable_stop', timetable_suffix),
            concat('timetable_journey', timetable_suffix)
            );

    -------------------------------
    -- Selecting ranked 1 files --
    -------------------------------

    RAISE NOTICE '% Selecting rank 1 files', clock_timestamp();

    execute format('DROP TABLE IF EXISTS public.%I', concat('timetable_stop_rank_1', timetable_suffix));

    execute format(
            '
            CREATE TABLE public.%I AS
            SELECT
              operator_ref AS operator_noc,
              service_code,
              line_name,
              filename AS xml_file_name,
              journey_code,
              date_of_journey,
              day_of_week,
              stop_name AS common_name,
              atco_code AS atco_code,
              stop_type,
              stop_index,
              lt AS stop_latitude,
              lon AS stop_longitude,
              locality_id,
              CAST(
                CONCAT(
                  (
                    CASE WHEN departure_day_shift IS TRUE
                          AND departure_time::TIME <= ''12:00:00''
                      THEN (date_of_journey + INTERVAL ''1'' DAY)::DATE
                    -- Handling journeys that run over midnight
                    WHEN last_departure::TIME < first_departure::TIME
                     -- There are some dq issues that get caught up in the first clause.
                     -- We can minimise that with the assumption that no journey:
                     -- a. starts before 22:00 and continues past midnight
                     -- b. starts before midnight and ends after 02:00
                     AND last_departure::TIME <= ''02:00:00''
                     AND first_departure::TIME >= ''22:00:00''
                      THEN (date_of_journey + INTERVAL ''1'' DAY)::DATE
                      ELSE date_of_journey END
                  )::TEXT,
                  '' '',
                  departure_time::TEXT
                ) AS TIMESTAMP
              ) AT TIME ZONE ''EUROPE/LONDON'' AS expected_departure_time,
              is_timing_point,
              LOWER(group_id) AS group_id,
              NULL AS otp_state,
              NULL AS actual_headway,
              NULL AS headway_time_difference,
              NULL AS siri_vm_position_id,
              NULL AS time_difference,
              nullif(stop_id, '''')::int AS stop_id,
              transmodel_servicepattern_id AS servicepattern_id,
              vehiclejourney_id,
              admin_area_id,
              row_number() OVER w AS real_index,
              count(*) OVER w AS max_index,
              direction,
              departure_day_shift
            FROM
              public.%I
            WHERE
              rk = 1 WINDOW w AS (
                PARTITION BY group_id,
                vehiclejourney_id
                ORDER BY
                  departure_time RANGE BETWEEN UNBOUNDED PRECEDING
                  AND UNBOUNDED FOLLOWING
              );
            ',
            concat('timetable_stop_rank_1', timetable_suffix),
            concat('timetable_stop', timetable_suffix)
            );

    ----------------------------
    --Removing last stop --
    ----------------------------

    RAISE NOTICE '% Removing last stop', clock_timestamp();

    execute format('DROP TABLE IF EXISTS public.%I', concat('timetable_stop_no_last_stops', timetable_suffix));

    execute format(
            '
            CREATE TABLE public.%I AS
            SELECT
              operator_noc,
              line_name,
              date_of_journey,
              stop_index,
              expected_departure_time,
              group_id,
              stop_id,
              real_index,
              direction
            FROM
              public.%I
            WHERE
              real_index != max_index;
            ',
            concat('timetable_stop_no_last_stops', timetable_suffix),
            concat('timetable_stop_rank_1', timetable_suffix)
            );

    -------------------------------------------------------------
    -- Add previous group id for frequent services no last stop--
    -------------------------------------------------------------

    RAISE NOTICE '% Adding previous_group_id', clock_timestamp();

    execute format('DROP TABLE IF EXISTS public.%I', concat('timetable_stop_prev_group_id', timetable_suffix));

    execute format(
            '
            CREATE TABLE public.%I AS
            SELECT
              operator_noc,
              line_name,
              date_of_journey,
              stop_index,
              expected_departure_time,
              group_id,
              CASE WHEN COUNT(*) OVER w >= 6 THEN LOWER(LAG(group_id) OVER w) ELSE NULL END AS previous_group_id,
              stop_id,
              real_index,
              direction
            FROM
              public.%I WINDOW w AS (
                PARTITION BY operator_noc,
                line_name,
                date_of_journey,
                stop_id,
                stop_index,
                extract(
                  HOUR
                  FROM
                    expected_departure_time
                )
                ORDER BY
                  expected_departure_time,
                  stop_index ASC RANGE BETWEEN UNBOUNDED PRECEDING
                  AND UNBOUNDED FOLLOWING
              );
            ',
            concat('timetable_stop_prev_group_id', timetable_suffix),
            concat('timetable_stop_no_last_stops', timetable_suffix)
            );

    ----------------------------
    -- Create dated partition --
    ----------------------------

    RAISE NOTICE '% (Re)Creating partition public.%', clock_timestamp(), tablename;


    execute format(
            'CREATE TABLE if not exists public.%I partition of public.%I FOR VALUES FROM (%L) TO (%L);',
            concat(tablename, '_p', longdatestring),
            tablename,
            partition_date,
            partition_date + interval '1' day);

    execute format('ALTER TABLE public.%I OWNER to abods_rw', concat(tablename, '_p', longdatestring));

    ------------------------------
    -- Deleting from partition --
    ------------------------------

    RAISE NOTICE '% Deleting from %', clock_timestamp(), tablename;

    execute format('DELETE FROM public.%I', concat(tablename, '_p', longdatestring));

    --------------------------
    --Importing to partition --
    --------------------------

    RAISE NOTICE '% Inserting into %', clock_timestamp(), tablename;

    execute format(
            '
            INSERT INTO
              public.%I (
                operator_noc,
                operator_name,
                service_code,
                line_name,
                xml_file_name,
                journey_code,
                date_of_journey,
                day_of_week,
                common_name,
                atco_code,
                stop_type,
                stop_index,
                stop_latitude,
                stop_longitude,
                locality_id,
                expected_departure_time,
                actual_departure_time,
                is_timing_point,
                group_id,
                previous_group_id,
                otp_state,
                expected_headway,
                actual_headway,
                headway_time_difference,
                siri_vm_position_id,
                time_difference,
                stop_id,
                off_set,
                servicepattern_id,
                vehiclejourney_id,
                admin_area_id,
                direction,
                departure_day_shift
              )
            SELECT
              tsr1.operator_noc,
              '''' AS operator_name,
              tsr1.service_code,
              tsr1.line_name,
              tsr1.xml_file_name,
              tsr1.journey_code,
              tsr1.date_of_journey,
              tsr1.day_of_week,
              tsr1.common_name,
              tsr1.atco_code,
              tsr1.stop_type,
              tsr1.stop_index,
              tsr1.stop_latitude,
              tsr1.stop_longitude,
              tsr1.locality_id,
              tsr1.expected_departure_time,
              NULL AS actual_departure_time,
              tsr1.is_timing_point,
              tsr1.group_id,
              LOWER(tspgi.previous_group_id) AS previous_group_id,
              tsr1.otp_state,
              extract(
                epoch
                FROM
                  tsr1.expected_departure_time::TIME - lag(tsr1.expected_departure_time::TIME) over (
                    PARTITION BY tsr1.operator_noc,
                    tsr1.line_name,
                    tsr1.date_of_journey,
                    tsr1.stop_id,
                    tsr1.stop_index
                    ORDER BY
                      tsr1.stop_id,
                      tsr1.stop_index,
                      tsr1.expected_departure_time::TIME ASC
                  )
              ) AS expected_headway,
              NULL AS actual_headway,
              NULL AS headway_time_difference,
              NULL AS siri_vm_position_id,
              NULL AS time_difference,
              tsr1.stop_id,
              extract(
                epoch
                FROM
                  tsr1.expected_departure_time::TIME - first_value(tsr1.expected_departure_time::TIME) over (
                    PARTITION BY tsr1.operator_noc,
                    tsr1.line_name,
                    tsr1.journey_code,
                    tsr1.date_of_journey
                    ORDER BY
                      tsr1.stop_index ASC
                  )
              ),
              tsr1.servicepattern_id,
              tsr1.vehiclejourney_id,
              tsr1.admin_area_id,
              tsr1.direction,
              tsr1.departure_day_shift
            FROM
              public.%I tsr1
              LEFT JOIN public.%I tspgi
                ON  tsr1.group_id = tspgi.group_id
                AND tsr1.direction = tspgi.direction
                AND tsr1.real_index = tspgi.real_index;
            ',
            concat(tablename, '_p', longdatestring),
            concat('timetable_stop_rank_1', timetable_suffix),
            concat('timetable_stop_prev_group_id', timetable_suffix)
            );

    --------------
    -- Clean Up --
    --------------

    IF SPLIT_PART(aurora_db_instance_identifier(), '-', 2) = 'sandbox' THEN
        RAISE NOTICE '% Skipping clean up', clock_timestamp();
    ELSE
        RAISE NOTICE '% Cleaning Up', clock_timestamp();

        execute format('DROP TABLE IF EXISTS public.%I', concat('organisation_timetable', timetable_suffix));
        execute format('DROP TABLE IF EXISTS public.%I', concat('filtered_registered_organisation_timetable', timetable_suffix));
        execute format('DROP TABLE IF EXISTS public.%I', concat('timetable_vehiclejourney', timetable_suffix));
        execute format('DROP TABLE IF EXISTS public.%I', concat('timetable_vehiclejourney_workingdays', timetable_suffix));
        execute format('DROP TABLE IF EXISTS public.%I', concat('timetable_vehiclejourney_exclusions', timetable_suffix));
        execute format('DROP TABLE IF EXISTS public.%I', concat('timetable_journey_workingdays_with_exclusions', timetable_suffix));
        execute format('DROP TABLE IF EXISTS public.%I', concat('timetable_vehiclejourney_servicecode_dupes', timetable_suffix));
        execute format('DROP TABLE IF EXISTS public.%I', concat('timetable_vehiclejourney_nodupes', timetable_suffix));
        execute format('DROP TABLE IF EXISTS public.%I', concat('timetable_journey', timetable_suffix));
        execute format('DROP TABLE IF EXISTS public.%I', concat('timetable_stop', timetable_suffix));
        execute format('DROP TABLE IF EXISTS public.%I', concat('timetable_vj_per_groupid', timetable_suffix));
        execute format('DROP TABLE IF EXISTS public.%I', concat('timetable_stop_rank_1', timetable_suffix));
        execute format('DROP TABLE IF EXISTS public.%I', concat('timetable_stop_no_last_stops', timetable_suffix));
        execute format('DROP TABLE IF EXISTS public.%I', concat('timetable_stop_prev_group_id', timetable_suffix));
        execute format('DROP TABLE IF EXISTS public.%I', concat('filtered_files', timetable_suffix));
    END IF;

    RAISE NOTICE '% generate_timetable complete', clock_timestamp();
end;
$$;

alter procedure generate_timetable owner to abods_proxy_rw;
