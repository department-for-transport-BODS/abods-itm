ALTER TABLE public."Timetable"
    ADD COLUMN IF NOT EXISTS registered BOOLEAN;


CREATE TABLE public.login_details (
    user_id INT primary key,
    data_monitoring_access_count INT,
    data_monitoring_last_accessed TIMESTAMP,
    last_login TIMESTAMP
);

ALTER TABLE public.login_details OWNER TO abods_proxy_rw;
