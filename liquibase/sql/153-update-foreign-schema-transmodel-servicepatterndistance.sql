IMPORT FOREIGN SCHEMA public LIMIT TO (
    transmodel_servicepatterndistance
)
FROM SERVER bods INTO bods;


GRANT SELECT ON TABLE bods.transmodel_servicepatterndistance TO abods_proxy_rw;
