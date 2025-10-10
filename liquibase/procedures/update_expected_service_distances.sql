CREATE OR REPLACE PROCEDURE public.update_expected_service_distances(
    IN partition_date date DEFAULT (CURRENT_DATE - '1 day'::interval)
)
LANGUAGE plpgsql
AS $procedure$
BEGIN
    WITH journeys AS (
        SELECT DISTINCT vehiclejourney_id, servicepattern_id
        FROM public."Timetable"
        WHERE date_of_journey = partition_date
    ),
    service_summary AS (
        SELECT 
            dt.servicepattern_id AS service_pattern_id,
            ej.noc_and_line_and_servicecode,
            ej.date_of_journey,
            COUNT(*) AS total_count,
            COUNT(*) FILTER (WHERE ej.avl_recorded = TRUE) AS avl_true_count,
            COUNT(*) FILTER (WHERE ej.avl_recorded IS DISTINCT FROM TRUE) AS avl_false_count
        FROM 
            public.expected_journeys ej
        JOIN 
            journeys dt
            ON dt.vehiclejourney_id = ej.vehicle_journey_id
        GROUP BY 
            dt.servicepattern_id,
            ej.noc_and_line_and_servicecode,
            ej.date_of_journey
    ),
    service_pattern_distances AS (
        SELECT 
            ss.date_of_journey,
            ss.service_pattern_id,
            ss.noc_and_line_and_servicecode,
            ss.total_count,
            ss.total_count * COALESCE(sd.coord_track_distance, sd.distance) AS total_distance, 
            ss.avl_true_count * COALESCE(sd.coord_track_distance, sd.distance) AS avl_true_distance
        FROM 
            service_summary ss
        JOIN 
            transmodel_servicepatterndistance sd
            ON ss.service_pattern_id = sd.service_pattern_id
    ),
    aggregated_distances AS (
        SELECT 
            spd.date_of_journey,
            spd.noc_and_line_and_servicecode,
            SUM(spd.total_distance) AS total_distance,
            SUM(spd.avl_true_distance) AS avl_true_distance
        FROM 
            service_pattern_distances spd
        GROUP BY 
            spd.date_of_journey,
            spd.noc_and_line_and_servicecode
    )
    UPDATE expected_services_by_date esbd
    SET 
        total_distance = ad.total_distance,
        avl_true_distance = ad.avl_true_distance
    FROM aggregated_distances ad
    WHERE 
        esbd.date_of_journey = ad.date_of_journey
        AND esbd.noc_and_line_and_servicecode = ad.noc_and_line_and_servicecode;

    REFRESH MATERIALIZED VIEW expected_services;
END;
$procedure$;

