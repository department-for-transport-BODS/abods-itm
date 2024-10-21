IMPORT FOREIGN SCHEMA public LIMIT TO (
    otc_operator
)
FROM SERVER bods INTO bods;

GRANT SELECT ON TABLE bods."otc_operator" TO abods_rw;
