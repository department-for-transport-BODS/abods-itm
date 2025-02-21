IMPORT FOREIGN SCHEMA public LIMIT TO (
    ui_lta
)
FROM SERVER bods INTO bods;

GRANT SELECT ON TABLE bods."UI_LTA" TO abods_rw;

CREATE TABLE public.ui_lta (
	id serial4 NOT NULL,
	"name" text NOT NULL,
	CONSTRAINT ui_lta_id_name_uniq UNIQUE (id, name),
	CONSTRAINT ui_lta_name_key UNIQUE (name),
	CONSTRAINT ui_lta_pkey PRIMARY KEY (id)
);
CREATE INDEX ui_lta_name_idx ON public.ui_lta USING btree (name text_pattern_ops);

select cron.schedule('update ui lta', '0 2 * * *',  $$call update_ui_lta();$$);