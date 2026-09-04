-- Keep management level separate from the free-text experience requirement.
BEGIN;

ALTER TABLE jobs
  ADD COLUMN IF NOT EXISTS job_level varchar(100);

COMMIT;
