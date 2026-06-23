CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_batch_batch_id
    ON public.batch USING btree (batch_id);
