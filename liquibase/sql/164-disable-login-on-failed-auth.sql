ALTER TABLE login_details
  ADD COLUMN failed_attempts INTEGER NOT NULL DEFAULT 0;