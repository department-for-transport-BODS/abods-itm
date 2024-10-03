
-- ADD INDEXES ON TIMETABLE TABLE ----

--- COMPOUND INDEX ON operator_noc, line_name and journey_code

CREATE INDEX compound_index_on_operator_noc_line_name_journey_code  
	ON public."Timetable" (operator_noc, line_name, journey_code); 

-- INDEX ON vehiclejourney_id

CREATE INDEX index_on_vehiclejourney_id    
	ON public."Timetable" (vehiclejourney_id); 

-- INDEX ON is_timing_point

CREATE INDEX index_on_is_timing_point 
	ON public."Timetable" (is_timing_point); 
