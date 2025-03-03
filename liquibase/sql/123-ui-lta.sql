IMPORT FOREIGN SCHEMA public LIMIT TO (
    ui_lta
)
FROM SERVER bods INTO bods;

GRANT SELECT ON TABLE bods."ui_lta" TO abods_proxy_rw;

CREATE TABLE IF NOT EXISTS public.ui_lta (
	id serial4 NOT NULL,
	"name" text NOT NULL,
	CONSTRAINT ui_lta_id_name_uniq UNIQUE (id, name),
	CONSTRAINT ui_lta_name_key UNIQUE (name),
	CONSTRAINT ui_lta_pkey PRIMARY KEY (id)
);
CREATE INDEX IF NOT EXISTS  ui_lta_name_idx ON public.ui_lta USING btree (name text_pattern_ops);

ALTER TABLE public.ui_lta OWNER TO abods_proxy_rw;

SELECT cron.schedule('update ui lta', '0 2 * * *',  $$CALL update_ui_lta();$$);
