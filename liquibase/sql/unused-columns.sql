ALTER TABLE abods.public."Alert"
    DROP COLUMN "alert_id";

ALTER TABLE abods.public."all_operators"
    DROP COLUMN "operatorid";

ALTER TABLE abods.public."ApiInfo"
    DROP COLUMN "timezone",
    DROP COLUMN "feature_flag_id";

ALTER TABLE abods.public."bods_user"
    DROP COLUMN "is_superuser",
    DROP COLUMN "is_active",
    DROP COLUMN "account_type",
    DROP COLUMN "admin_org";

ALTER TABLE abods.public."expected_journeys"
    DROP COLUMN "line_name",
    DROP COLUMN "journey_code",
    DROP COLUMN "stop_count",
    DROP COLUMN "vehicle_journey_id",
    DROP COLUMN "day_of_week",
    DROP COLUMN "journey_code",
    DROP COLUMN "admin_area_id";

ALTER TABLE abods.public."feed_monitor_minute_summary"
    DROP COLUMN "live_locations";

ALTER TABLE abods.public."feed_monitor_summary"
    DROP COLUMN "id";

ALTER TABLE abods.public."naptan_adminarea"
    DROP COLUMN "traveline_region_id",
    DROP COLUMN "atco_code",
    DROP COLUMN "ui_lta_id";

ALTER TABLE abods.public."naptan_adminarea_with_shape"
    DROP COLUMN "atco_code";

ALTER TABLE abods.public."naptan_locality"
    DROP COLUMN "easting",
    DROP COLUMN "northing",
    DROP COLUMN "district_id";

ALTER TABLE abods.public."naptan_stoppoint_latlong"
    DROP COLUMN "naptan_code",
    DROP COLUMN "street",
    DROP COLUMN "indicator",
    DROP COLUMN "stop_areas",
    DROP COLUMN "bus_stop_type",
    DROP COLUMN "stop_type";

ALTER TABLE abods.public."performance_statistics"
    DROP COLUMN "service_name",
    DROP COLUMN "total_count",
    DROP COLUMN "trend_period_start",
    DROP COLUMN "trend_period_end",
    DROP COLUMN "trend_total_count",
    DROP COLUMN "percentage_change";

ALTER TABLE abods.public."SiriVMPositions"
    DROP COLUMN "siri_vm_positions_id",
    DROP COLUMN "batch_id",
    DROP COLUMN "response_time_stamp",
    DROP COLUMN "load_time_stamp",
    DROP COLUMN "origin_ref",
    DROP COLUMN "destination_ref",
    DROP COLUMN "departure_time";

ALTER TABLE abods.public."Timetable"
    DROP COLUMN "operator_name",
    DROP COLUMN "xml_file_name",
    DROP COLUMN "journey_code",
    DROP COLUMN "day_of_week",
    DROP COLUMN "atco_code",
    DROP COLUMN "stop_type",
    DROP COLUMN "locality_id",
    DROP COLUMN "previous_group_id",
    DROP COLUMN "expected_headway",
    DROP COLUMN "actual_headway",
    DROP COLUMN "headway_time_difference",
    DROP COLUMN "siri_vm_position_id",
    DROP COLUMN "time_difference",
    DROP COLUMN "load_time_stamp",
    DROP COLUMN "off_set",
    DROP COLUMN "servicepattern_id",
    DROP COLUMN "admin_area_id",
    DROP COLUMN "departure_day_shift";

ALTER TABLE abods.public."timetable_frequent_summary_services"
    DROP COLUMN "service_code",
    DROP COLUMN "line_name",
    DROP COLUMN "avg_time_difference";

ALTER TABLE abods.public."timetable_summary_operator_t"
    DROP COLUMN "avg_time_difference";

ALTER TABLE abods.public."timetable_summary_service_tz"
    DROP COLUMN "timetable_id";

ALTER TABLE abods.public."timetable_summary_stops_tz"
    DROP COLUMN "timetable_id",
    DROP COLUMN "line_name";

ALTER TABLE abods.public."timetable_threshold_summary"
    DROP COLUMN "line_name",
    DROP COLUMN "service_name",
    DROP COLUMN "departure_hour";
