ALTER TABLE public."Timetable"
    ADD COLUMN IF NOT EXISTS registered BOOLEAN;


CREATE TABLE public.login_details (
    user_id INT NOT NULL,
    data_monitoring_access_count INT,
    data_monitoring_last_accessed TIMESTAMP
);

CREATE INDEX if not exists login_details_idx ON public.login_details USING btree (user_id);

ALTER TABLE public.login_details OWNER TO abods_proxy_rw;
