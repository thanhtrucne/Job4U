-- Criteria shared by applicant job preferences and recruiter job listings.
BEGIN;

ALTER TABLE digital_profiles
  ADD COLUMN IF NOT EXISTS desired_job_level varchar(100),
  ADD COLUMN IF NOT EXISTS desired_job_type varchar(100);

COMMIT;
