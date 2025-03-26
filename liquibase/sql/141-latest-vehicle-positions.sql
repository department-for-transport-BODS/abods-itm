CREATE TABLE IF NOT EXISTS public.latest_vehicle_positions
(
    operator_ref     text                     not null,
    vehicle_ref      text                     not null,
    line_name        text                     not null,
    journey_ref      text                     not null,
    direction_ref    text                     not null,
    recorded_at_time timestamp with time zone not null,
    latitude         real                     not null,
    longitude        real                     not null,
    group_id         text                     not null,
    constraint latest_vehicle_positions_primary_key
        primary key (operator_ref, vehicle_ref)
);
