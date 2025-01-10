create or replace procedure update_performance_statistics_v4()
    language plpgsql
as
$$

DECLARE
    start_date           DATE;
    end_date             DATE;
    trend_start_date     DATE;
    trend_end_date       DATE;
    current_period_stats RECORD;
    trend_period_stats   RECORD;
    period_type          VARCHAR;
    period_types         TEXT[]    := ARRAY ['last_7_days', 'last_28_days', 'month_to_date', 'last_month'];
    is_timing_point_var  BOOLEAN;
    is_timing_points     BOOLEAN[] := ARRAY [TRUE, FALSE];

BEGIN

    EXECUTE format('DELETE FROM public.performance_statistics');
    RAISE NOTICE 'Deleting the old starts';

    FOREACH period_type IN ARRAY period_types
        LOOP

            CALL get_date_range(period_type, start_date, end_date);
            CALL get_trend_date_range(period_type, trend_start_date, trend_end_date);


            FOREACH is_timing_point_var IN ARRAY is_timing_points
                LOOP
                    RAISE NOTICE 'Timing Point %', is_timing_point_var;

                    EXECUTE format('DROP TABLE IF EXISTS temp_current_stats_%s_%s', period_type, is_timing_point_var);
                    EXECUTE format('DROP TABLE IF EXISTS temp_trend_stats_%s_%s', period_type, is_timing_point_var);


                    -- Create temporary tables for current and trend statistics
                    EXECUTE format('
				CREATE TEMP TABLE temp_current_stats_%s_%s AS
					SELECT
						ttbl.operator_noc,
						ttbl.line_name,
						ttbl.noc_and_line_and_servicecode,
						-- ttbl.service_name,
						ttbl.is_timing_point,
						ttbl.on_time_count,
						ttbl.early_count,
						ttbl.late_count,
						ttbl.total_count
					FROM (
						SELECT
							operator_noc,
							line_name,
							noc_and_line_and_servicecode,
							-- service_name,
							is_timing_point,
							SUM(on_time_count) AS on_time_count,
							SUM(early_count) AS early_count,
							SUM(late_count) AS late_count,
							SUM(on_time_count + early_count + late_count) AS total_count
						FROM public.timetable_summary_service_tz
						WHERE
							is_timing_point = %L
							AND date_of_journey BETWEEN ''%s'' AND ''%s''
						GROUP BY
							operator_noc,
							line_name,
							noc_and_line_and_servicecode,
							-- service_name,
							is_timing_point
					) AS ttbl;
					', period_type, is_timing_point_var, is_timing_point_var, start_date, end_date);
                    -- Create temporary tables for current and trend statistics
                    EXECUTE format('
				CREATE TEMP TABLE temp_trend_stats_%s_%s AS
					SELECT
						ttbl.operator_noc,
						ttbl.line_name,
						ttbl.noc_and_line_and_servicecode,
						-- ttbl.service_name,
						ttbl.is_timing_point,
						ttbl.trend_on_time_count,
						ttbl.trend_early_count,
						ttbl.trend_late_count,
						ttbl.trend_total_count
					FROM (
						SELECT
							operator_noc,
							line_name,
							noc_and_line_and_servicecode,
							-- service_name,
							is_timing_point,
							SUM(on_time_count) AS trend_on_time_count,
							SUM(early_count) AS trend_early_count,
							SUM(late_count) AS trend_late_count,
							SUM(on_time_count + early_count + late_count) AS trend_total_count
						FROM public.timetable_summary_service_tz
						WHERE
							is_timing_point = %L
							AND date_of_journey BETWEEN ''%s'' AND ''%s''
						GROUP BY
							operator_noc,
							line_name,
							noc_and_line_and_servicecode,
							-- service_name,
							is_timing_point
					) AS ttbl;
					', period_type, is_timing_point_var, is_timing_point_var, trend_start_date, trend_end_date);

                    --- Calculate performance for current period
                    EXECUTE format('

				INSERT INTO public.performance_statistics(
					operator_noc,
					line_name,
					noc_and_line_and_servicecode,
		    		-- service_name,
					is_timing_point,
					date_period_start,
					date_period_end,
					period_type,
					on_time_count,
					early_count,
					late_count,
					total_count,
					on_time_percentage,
					trend_period_start,
					trend_period_end,
					trend_on_time_count,
					trend_early_count,
					trend_late_count,
					trend_total_count,
					trend_percentage,
					percentage_change
				)
				SELECT
					c.operator_noc,
					c.line_name,
					c.noc_and_line_and_servicecode,
		    		-- c.service_name,
					c.is_timing_point,
					''%s'' AS date_period_start,
					''%s'' AS date_period_end,
					''%s'' AS period_type,
					c.on_time_count,
					c.early_count,
					c.late_count,
					c.total_count,
					CASE WHEN c.total_count = 0 THEN 0 ELSE (c.on_time_count::FLOAT / c.total_count)*100 END,
					''%s'' AS trend_period_start,
					''%s'' AS trend_period_end,
					t.trend_on_time_count,
					t.trend_early_count,
					t.trend_late_count,
					t.trend_total_count,
					CASE WHEN t.trend_total_count = 0 THEN 0 ELSE (t.trend_on_time_count::FLOAT / t.trend_total_count)*100 END,
					CASE
					    WHEN c.total_count = 0 AND t.trend_total_count = 0 THEN 0
					    WHEN c.total_count = 0 THEN -((t.trend_on_time_count::FLOAT / t.trend_total_count)*100)
					    WHEN t.trend_total_count = 0 THEN (c.on_time_count::FLOAT / c.total_count)*100
					    ELSE ((c.on_time_count::FLOAT / c.total_count)*100) - ((t.trend_on_time_count::FLOAT / t.trend_total_count)*100)
					END AS percentage_change
				FROM temp_current_stats_%s_%s c
				LEFT JOIN temp_trend_stats_%s_%s t
				ON c.operator_noc = t.operator_noc
				AND c.line_name = t.line_name
				AND c.noc_and_line_and_servicecode = t.noc_and_line_and_servicecode
				-- AND c.service_name = t.service_name
				;
				', start_date, end_date, period_type, trend_start_date, trend_end_date, period_type,
                                   is_timing_point_var, period_type, is_timing_point_var);
                END LOOP;
        END LOOP;
END
$$;

alter procedure update_performance_statistics_v4 owner to abods_proxy_rw;
