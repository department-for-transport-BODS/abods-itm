ALTER TABLE public."Tokens" ADD COLUMN IF NOT EXISTS expires timestamp DEFAULT (now() + INTERVAL '7' DAY)
