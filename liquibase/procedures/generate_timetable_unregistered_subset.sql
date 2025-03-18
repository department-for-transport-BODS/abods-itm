create or replace procedure generate_timetable_unregistered_subset(IN partition_date date)
    language plpgsql
as
$$

declare
    longdatestring   text := to_char(partition_date, 'YYYY_MM_DD');
    timetable_suffix text := concat('_unregistered_subset_', longdatestring);
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

    RAISE NOTICE '% (Re)Creating filtered_unregistered_organisation_timetable table', clock_timestamp();

    execute format('DROP TABLE IF EXISTS public.%I', concat('filtered_unregistered_organisation_timetable', timetable_suffix));

    execute format(
            '
            CREATE TABLE public.%I AS
            SELECT
              *
            FROM
              (
                WITH already_processed_service_codes AS (
                  SELECT
                    DISTINCT service_code,
                    line_name
                  FROM
                    public.%I
                ),
                split_otc_table_license_line AS (
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
                missing_from_timetable AS (
                  --from all data, what hasnt been processed already
                  SELECT
                    stll.*
                  FROM
                    split_timetables_license_line stll
                    LEFT JOIN already_processed_service_codes apsc ON
                      stll.service_code = apsc.service_code
                  WHERE
                    apsc.service_code IS NULL
                ),
                flag_registered AS (
                  -- flag the registered services
                  SELECT
                    mft.license_line,
                    service_code,
					split_service_number,
                  	txcfileattributes_id,
                  	national_operator_code,
                  	filename,
                  	revision_id,
                  	revision_number,
                    (otc.license_line IS NOT NULL) AS registered
                  FROM
                    missing_from_timetable mft
                    LEFT JOIN split_otc_table_license_line otc ON
                      LOWER(otc.license_line) = LOWER(mft.license_line)
                )
                SELECT
                  DISTINCT service_code,
                  registered,
                  split_service_number AS line_name,
                  txcfileattributes_id,
                  national_operator_code,
                  filename,
                  revision_id,
                  revision_number, 
				  license_line
                FROM
                  flag_registered
              );
            ',
            concat('filtered_unregistered_organisation_timetable', timetable_suffix),
            concat(tablename, '_p', longdatestring),
            concat('organisation_timetable', timetable_suffix)
            );
           
           
    RAISE NOTICE '% (Re)Setting flag to true ', clock_timestamp();

    execute format('DROP TABLE IF EXISTS public.%I', concat('timetable_flag_true', timetable_suffix));

    execute format(
            '
            UPDATE public.%I a
			SET registered = TRUE
			where license_line in (''PB0001484597'',
			''PB0001484C3'',
			''PB000148453'',
			''PB000148453A'',
			''PB0001484PRO'',
			''PB0001484677'',
			''PB000148470'',
			''PB0001484217'',
			''PB0001484218'',
			''PB0001484219'',
			''PB000148412'',
			''PB000148414'',
			''PB000148450'',
			''PB0001484343'',
			''PB000148411'',
			''PB000148435'',
			''PB0001484620'',
			''PB0001484173'',
			''PB0001484277'',
			''PB0001484255'',
			''PB0001484256'',
			''PB000198720'',
			''PB0001987980'',
			''PB00021861'',
			''PB00021863A'',
			''PB00021863B'',
			''PB00021863C'',
			''PB0002186C'',
			''PB000240437'',
			''PB000240438'',
			''PB000240438A'',
			''PB0002711COT'',
			''PB0002711KC'',
			''PB0002711SN'',
			''PB0002711IGO'',
			''PB0002711RM'',
			''PB0002711RV1'',
			''PB0002711SNX'',
			''PB0002711CC'',
			''PB0003954AD12'',
			''PB1049268846'',
			''PB1057218476'',
			''PB1081341Golden_Tours_Hop_On_Hop_Off'',
			''PB1081341Golden_Tours_Hop_On_Hop_Off'',
			''PB1083854ML1'',
			''PB2003801MED1'',
			''PB2003801MED2'',
			''PB2044957FTB'',
			''PC0001086TP'',
			''PC0001086TP'',
			''PC0001135SW'',
			''PC000113590'',
			''PC0001135CMT'',
			''PC0001135HQ'',
			''PC0001135IF'',
			''PC0001135RA'',
			''PC0001135RA'',
			''PC0001135TA'',
			''PC00011356'',
			''PC00011356.1'',
			''PC00011356.2'',
			''PC00011356.3'',
			''PC00011356.4'',
			''PC00011356E'',
			''PC00011356N'',
			''PC00011356X'',
			''PC0001135TM'',
			''PC0001135V1'',
			''PC0001135V3'',
			''PC0001141699'',
			''PC000114186'',
			''PC000114186A'',
			''PC0002407516'',
			''PC0002407X4'',
			''PC0002407X5'',
			''PC0002407685'',
			''PC0002407S11'',
			''PC0002407S15'',
			''PC0002407S22'',
			''PC0002407530'',
			''PC000240742'',
			''PC0003713359'',
			''PC0003713360'',
			''PC0004741646'',
			''PC000513712A'',
			''PC000513712C'',
			''PC00051373'',
			''PC0005248X41'',
			''PC1033334721'',
			''PC103333497'',
			''PC103333497A'',
			''PC1033334127'',
			''PC1033334280'',
			''PC1033334280'',
			''PC1033334584'',
			''PC1033334923'',
			''PC1033334241'',
			''PC10414915'',
			''PC10414916'',
			''PC10414915'',
			''PC10414916'',
			''PC108917214'',
			''PC1094200101'',
			''PC1094200BET'',
			''PC2044596X70'',
			''PC2063115SPLASH01'',
			''PD000047931'',
			''PD000047978'',
			''PD0000790CAT2'',
			''PD0000790CAT4'',
			''PD0000790CAT1'',
			''PD0000790CAT5'',
			''PD000100790'',
			''PD000100792'',
			''PD000100791'',
			''PD1050801112'',
			''PF0000069320'',
			''PF0000070TN162'',
			''PF0000070TN164'',
			''PF0000089ThomasMills1'',
			''PF0000089ThomasMills2'',
			''PF00001477'',
			''PF00001471'',
			''PF00001472'',
			''PF0000224ZIP'',
			''PF0000224ZIP2'',
			''PF0000224ZIP3'',
			''PF0000323A'',
			''PF0000323D'',
			''PF0000323A'',
			''PF0000323D'',
			''PF0000323A'',
			''PF0000323D'',
			''PF0000804FWC005'',
			''PF0001449X10'',
			''PF0001449Shuttle'',
			''PF000149310'',
			''PF0002189717'',
			''PF0002189502'',
			''PF0002252Walk and Ride'',
			''PF000225240'',
			''PF000225240A'',
			''PF000225240B'',
			''PF0002280402'',
			''PF0007024N100S'',
			''PF0007038354'',
			''PF0007038510'',
			''PF0007038548'',
			''PF0007038533'',
			''PF000703810'',
			''PF000703812'',
			''PF000703812A'',
			''PF0007038574'',
			''PF0007038NG1'',
			''PF0007062S112S'',
			''PF0007062S156S'',
			''PF0007062S148S'',
			''PF00070625178B'',
			''PF0007062SLE15'',
			''PF0007109S137S'',
			''PF0007109S138S'',
			''PF0007109S132S'',
			''PF0007109S139S'',
			''PF0007157SP'',
			''PF0007157SKY'',
			''PF1018256CH1'',
			''PF101825615'',
			''PF101825615A'',
			''PF101825616'',
			''PF101825617'',
			''PF101825619'',
			''PF101825620'',
			''PF1110807CON715'',
			''PF1116442PR'',
			''PF111839483'',
			''PF1125306BTS'',
			''PF1129415WellandWandererEast'',
			''PF1129415WellandWandererWest'',
			''PF1129415WellandWandererWest'',
			''PF1129415ChattyBus5'',
			''PF1129415ChattyBus4'',
			''PF1129415ChattyBus2'',
			''PF1135558S116S'',
			''PF1135558S125S'',
			''PF200613038'',
			''PF200613038A'',
			''PF2006130ND'',
			''PF2020005331'',
			''PF2020005331'',
			''PG0000421AZ10'',
			''PG1115480T8'',
			''PH0000135T1E'',
			''PH0000135372'',
			''PH0004983MOUS'',
			''PH000503186'',
			''PH0005031620'',
			''PH000503113'',
			''PH000503112'',
			''PH0005031S6'',
			''PH0005031807'',
			''PH0005305863'',
			''PH0005305COLY9'',
			''PH0005305COLY5'',
			''PH0005305TG001'',
			''PH0005305TG003'',
			''PH0005305TG004'',
			''PH0005305TG005'',
			''PH0005305TG002'',
			''PH0005727BV1'',
			''PH0005863488'',
			''PH0005863489'',
			''PH0006008CS1'',
			''PH0007054TS3'',
			''PH0007054TS1'',
			''PH0007054TS2'',
			''PH103859912'',
			''PH1081198162'',
			''PH1081198162'',
			''PH1120297DuckTour'',
			''PH1121126ST'',
			''PH1121126QC'',
			''PH1130867KLB8'',
			''PH1145323KBC301'',
			''PH1145323CPR300'',
			''PH203823631'',
			''PH2050218AX005'',
			''PK0001213ESS'',
			''PK0001816E'',
			''PK0003171STP2'',
			''PK0003171STP1'',
			''PK1147727Meopham1'',
			''PK1147727VIGO1'',
			''PK2055656HRC1'')
            ',

            concat('filtered_unregistered_organisation_timetable', timetable_suffix)
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
            concat('filtered_unregistered_organisation_timetable', timetable_suffix),
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
                ) AS group_id,
                registered
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
              departure_day_shift,
              registered
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
              LAST_VALUE(departure_time) OVER w AS last_departure,
              registered
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
              registered
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
                reprocessing_required
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
              tsr1.departure_day_shift,
              tsr1.registered,
              true
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

alter procedure generate_timetable_unregistered_subset owner to abods_proxy_rw;
