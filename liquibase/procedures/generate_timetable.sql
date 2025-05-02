create or replace procedure generate_timetable(IN partition_date date)
    language plpgsql
as
$$

declare
    longdatestring   text := to_char(partition_date, 'YYYY_MM_DD');
    timetable_suffix text := concat('_', longdatestring);
    tablename        text := 'Timetable';
    is_future        BOOLEAN;
   
begin
	
    is_future := (partition_date > now());
   
    if is_future then
	RAISE NOTICE '% is_future flag set to: True', clock_timestamp();
    else 
        RAISE NOTICE '% is_future flag set to: False', clock_timestamp();
    end if;
        RAISE NOTICE '% (Re)Creating filtered_files temp table', clock_timestamp();

    execute format('DROP TABLE IF EXISTS public.%I', concat('filtered_files', timetable_suffix));

    IF is_future THEN
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

    IF is_future THEN
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
                  ) osn ON LOWER(ot.service_code) = LOWER(osn.otc_service_code)
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
              ts2.line_name AS exploded_line_name,
              (reg_services.service_code is not null) AS registered
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
                ON ts2.id = tv.service_pattern_id
              LEFT JOIN public.%I reg_services
                ON LOWER(reg_services.service_code) = LOWER(a.service_code);
            ',
            concat('timetable_vehiclejourney', timetable_suffix),
            partition_date,
            concat('organisation_timetable', timetable_suffix),
            partition_date,
            concat('filtered_registered_organisation_timetable', timetable_suffix),
            partition_date
            );
           
    else 

    execute format(
            '
            CREATE TABLE public.%I AS
            SELECT
              *
            FROM
              (
                WITH split_otc_table_license_line AS (
                  --create license line concat for all registered data
                  SELECT
                    DISTINCT registration_number,
                    concat(
                      split_part(registration_number, ''/'', 1),
                      split_service_number
                    ) AS license_line
                  FROM
                    bods.otc_service
                    CROSS JOIN LATERAL unnest(string_to_array(service_number, ''|'')) AS split_service_number
                ),
                split_timetables_license_line AS (
                  --create license line concat for all timetable data published
                  SELECT
                    *,
                    concat(
                      split_part(service_code, '':'', 1),
                      split_service_number
                    ) AS license_line
                  FROM
                    public.%I
                    CROSS JOIN LATERAL unnest(line_name) AS split_service_number
                ),
                flag_registered AS (
                  -- flag the registered services
                  SELECT
                    *,
                    (otc.license_line IS NOT NULL OR lldqi.dq_issues_license_line IS NOT NULL) AS registered
                  FROM
                    split_timetables_license_line mft
                    LEFT JOIN split_otc_table_license_line otc ON
                      LOWER(otc.license_line) = LOWER(mft.license_line)
					LEFT JOIN public.license_line_data_quality_issues lldqi ON
						LOWER(lldqi.dq_issues_license_line) = LOWER(mft.license_line)
                )
                SELECT
                  DISTINCT service_code,
                  registered,
                  split_service_number AS line_name,
                  txcfileattributes_id,
                  national_operator_code,
                  filename,
                  revision_id,
                  revision_number
                FROM
                  flag_registered
              );
            ',
            concat('filtered_registered_organisation_timetable', timetable_suffix),
            concat('organisation_timetable', timetable_suffix)
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
                AND ts2.line_name = a.line_name
              JOIN public.transmodel_vehiclejourney tv
                ON ts2.id = tv.service_pattern_id;
            ',
            concat('timetable_vehiclejourney', timetable_suffix),
            partition_date,
            concat('filtered_registered_organisation_timetable', timetable_suffix),
            partition_date
            );
           
    end if;

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
                  TRIM(national_operator_code),
                  TRIM(exploded_line_name),
                  TRIM(journey_code),
                  date_of_journey
                ) AS group_id,
                registered
              FROM
                public.%I tvw
              WHERE
                trim(tvw.journey_code) <> '''' WINDOW w AS (
                  PARTITION BY LOWER(TRIM(national_operator_code)),
                  LOWER(TRIM(exploded_line_name)),
                  LOWER(TRIM(journey_code)),
                  date_of_journey,
                  LOWER(TRIM(direction))
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
              departure_day_shift,
              registered,
              stop.stop_activity_id as stop_activity_id
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
              b.id AS stop_id,
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
              LAST_VALUE(departure_time) OVER w AS last_departure,
              registered,
              stop_activity_id
            FROM
              public.%I a
              JOIN public.naptan_stoppoint b
                ON LOWER(a.atco_code) = LOWER(b.atco_code)
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
                     -- a. starts before 20:00 and continues past midnight
                     -- b. starts before midnight and ends after 04:00
                     -- (note: journeys longer than 5h exist, but the longest across midnight is no more than 3 hours either side)
                     AND first_departure::TIME >= ''20:00:00''
                     AND last_departure::TIME <= ''04:00:00''
                     -- We only need to modify the date of the departure time for the stops that come after midnight
                     AND departure_time::TIME <= ''04:00:00''
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
              departure_day_shift,
              registered,
              stop_activity_id in (2,7) AS set_down
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

    -------------------------------------------------------------
    -- Add previous group id for frequent services no last stop--
    -------------------------------------------------------------

    RAISE NOTICE '% Adding previous_group_id', clock_timestamp();

    execute format('DROP TABLE IF EXISTS public.%I', concat('timetable_stop_prev_group_id', timetable_suffix));

    execute format(
            '
            CREATE TABLE public.%I AS WITH trip_stop_sequences AS (
              SELECT
                t.group_id,
                t.line_name,
                t.operator_noc,
                t.direction,
                t.vehiclejourney_id,
                STRING_AGG(
                  CAST(t.stop_id AS VARCHAR),
                  ''|''
                  ORDER BY
                    expected_departure_time
                ) AS route_id,
                Min(expected_departure_time) AS departure_time,
                Max(expected_departure_time) AS final_arrival
              FROM
                public.%I t
              GROUP BY
                t.group_id,
                t.vehiclejourney_id,
                t.line_name,
                t.operator_noc,
                t.direction
            ),
            sliding_window_counts AS (
              SELECT
                d1.route_id,
                d1.line_name,
                d1.operator_noc,
                d1.group_id,
                d1.direction,
                d1.departure_time,
                d1.final_arrival,
                d1.vehiclejourney_id,
                COUNT(*) over(
                  PARTITION BY d1.route_id,
                  d1.line_name,
                  d1.operator_noc,
                  d1.direction
                  ORDER BY
                    d1.departure_time RANGE BETWEEN CURRENT ROW
                    AND interval ''60 minutes 0 seconds'' FOLLOWING
                ) AS departures_in_window_hour_after,
                COUNT(*) over(
                  PARTITION BY d1.route_id,
                  d1.line_name,
                  d1.operator_noc,
                  d1.direction
                  ORDER BY
                    d1.departure_time RANGE BETWEEN interval ''60 minutes 0 seconds'' PRECEDING
                    AND CURRENT ROW
                ) AS departures_in_window_hour_before,
                COUNT(*) over(
                  PARTITION BY d1.route_id,
                  d1.line_name,
                  d1.operator_noc,
                  d1.direction
                  ORDER BY
                    d1.departure_time RANGE BETWEEN CURRENT ROW
                    AND interval ''30 minutes 0 seconds'' FOLLOWING
                ) + COUNT(*) over(
                  PARTITION BY d1.route_id,
                  d1.line_name,
                  d1.operator_noc,
                  d1.direction
                  ORDER BY
                    d1.departure_time RANGE BETWEEN interval ''30 minutes 0 seconds'' PRECEDING
                    AND CURRENT ROW
                ) -1 AS departures_in_window_hour_surrounding
              FROM
                trip_stop_sequences d1
            ),
            frequent_services AS (
              SELECT
                *,
                -- Identify if this is part of a frequent batch (6+ departures in surrounding hour)
                (
                  departures_in_window_hour_before >= 6
                  OR departures_in_window_hour_after >= 6
                  OR departures_in_window_hour_surrounding >= 6
                ) AS is_frequent,
                -- Identify if this is the first in a frequent batch
                (
                  departures_in_window_hour_after >= 6
                  AND departures_in_window_hour_surrounding < 6
                  AND departures_in_window_hour_before < 6
                  AND (
                    (
                      LAG(departures_in_window_hour_after < 6) OVER w
                      AND LAG(departures_in_window_hour_surrounding < 6) OVER w
                    )
                    OR LAG(departures_in_window_hour_surrounding < 6) OVER w ISNULL
                  )
                ) AS is_first_in_frequent_batch,
                LAG(group_id) OVER w AS previous_group_id
              FROM
                sliding_window_counts d1 WINDOW w AS (
                  PARTITION BY line_name,
                  operator_noc,
                  route_id,
                  direction
                  ORDER BY
                    departure_time
                )
            )
            SELECT
              t.operator_noc,
              t.service_code,
              t.line_name,
              t.xml_file_name,
              t.journey_code,
              t.date_of_journey,
              t.day_of_week,
              t.common_name,
              t.atco_code,
              t.stop_type,
              t.stop_index,
              t.stop_latitude,
              t.stop_longitude,
              t.locality_id,
              t.expected_departure_time,
              t.is_timing_point,
              t.group_id,
              t.otp_state,
              t.stop_id,
              t.servicepattern_id,
              t.vehiclejourney_id,
              t.admin_area_id,
              t.direction,
              t.departure_day_shift,
              t.registered,
              CASE
                WHEN f.is_frequent
                 AND f.is_first_in_frequent_batch
                    THEN ''FIRST_SERVICE'' --identifier for the first journey in a frequent services block, e.g. if frequent 7-8am and 5-6pm- the 7am and 5pm journey
                WHEN f.is_frequent
                 AND t.expected_departure_time = f.final_arrival
                    THEN ''LAST_STOP'' --identifier for last stop in a frequent service journey
                WHEN f.is_frequent
                    THEN f.previous_group_id
                ELSE NULL
              END AS previous_group_id,
	      t.set_down
            FROM
              public.%I t
              LEFT JOIN frequent_services f ON f.vehiclejourney_id = t.vehiclejourney_id;
            ',
            concat('timetable_stop_prev_group_id', timetable_suffix),
            concat('timetable_stop_rank_1', timetable_suffix),
            concat('timetable_stop_rank_1', timetable_suffix)
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
                departure_day_shift,
                registered,
                reprocessing_required,
                set_down
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
              LOWER(tsr1.previous_group_id) AS previous_group_id,
              tsr1.otp_state,
              NULL AS expected_headway,
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
              tsr1.departure_day_shift,
              tsr1.registered,
              NULL,
              tsr1.set_down
            FROM
              public.%I tsr1;
            ',
            concat(tablename, '_p', longdatestring),
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
        execute format('DROP TABLE IF EXISTS public.%I', concat('timetable_stop_prev_group_id', timetable_suffix));
        execute format('DROP TABLE IF EXISTS public.%I', concat('filtered_files', timetable_suffix));
    END IF;

    RAISE NOTICE '% generate_timetable complete', clock_timestamp();
end;
$$;

alter procedure generate_timetable owner to abods_proxy_rw;
