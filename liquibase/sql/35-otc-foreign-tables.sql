IMPORT FOREIGN SCHEMA public LIMIT TO (
    otc_service,
    otc_inactiveservice
)
FROM SERVER bods INTO bods;

GRANT SELECT ON TABLE bods."otc_service" TO abods_rw;
GRANT SELECT ON TABLE bods."otc_inactiveservice" TO abods_rw;