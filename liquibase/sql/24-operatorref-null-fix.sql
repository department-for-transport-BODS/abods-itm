CREATE OR REPLACE VIEW public.all_operators
as SELECT oo.id AS operatorid,
	case 
		when to2.noc_code is not null then to2.noc_code
		else oo.noc 
    end as operatorref,
    CASE
        WHEN to2.name IS NULL THEN concat('Not in Traveline: ', oo.noc)::character varying
        ELSE to2.name
    END AS name
FROM bods.organisation_operatorcode oo
FULL JOIN traveline_operators to2 ON oo.noc::text = to2.noc_code::text
GROUP BY 
	oo.id,
	case 
		when to2.noc_code is not null then to2.noc_code
		else oo.noc 
    end,
	CASE
	    WHEN to2.name IS NULL THEN concat('Not in Traveline: ', oo.noc)::character varying
	    ELSE to2.name
    end;

 ALTER VIEW public.all_operators  OWNER TO abods_rw;