CREATE TABLE IF NOT EXISTS public.login_details
(
    user_id                        INT       NOT NULL PRIMARY KEY,
    last_login                     TIMESTAMP NOT NULL,
    data_monitoring_access_count   INT,
    data_monitoring_access_refresh TIMESTAMP
);

ALTER TABLE public.login_details
    OWNER TO abods_proxy_rw;

INSERT INTO public.login_details (user_id, last_login)
SELECT user_id, (expires - INTERVAL '14' DAY)
FROM public."Tokens"
WHERE user_id NOT IN (SELECT user_id FROM public.login_details);
