create or replace view all_operators(operatorid, operatorref, name) as
SELECT oo.id   AS operatorid,
       CASE
           WHEN to2.noc_code IS NOT NULL THEN to2.noc_code
           ELSE oo.noc
           END AS operatorref,
       CASE
           WHEN to2.name IS NULL THEN concat('Not in Traveline: ', oo.noc)::character varying
           ELSE to2.name
           END AS name
FROM bods.organisation_operatorcode oo
         FULL JOIN traveline_operators to2 ON oo.noc::text = to2.noc_code::text
GROUP BY oo.id,
         (
             CASE
                 WHEN to2.noc_code IS NOT NULL THEN to2.noc_code
                 ELSE oo.noc
                 END),
         (
             CASE
                 WHEN to2.name IS NULL THEN concat('Not in Traveline: ', oo.noc)::character varying
                 ELSE to2.name
                 END);
