ALTER TABLE public."Tokens" 
ADD COLUMN data_monitoring_access_count INT NULL,
ADD COLUMN data_monitoring_last_accessed TIMESTAMP NULL;
