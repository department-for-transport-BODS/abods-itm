create or replace view bods_operators(operatorid, operatorref) as
SELECT id  AS operatorid,
       noc AS operatorref
FROM bods.organisation_operatorcode oo
GROUP BY id, noc;

alter view bods_operators owner to abods_proxy_rw;
