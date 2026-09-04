-- Recruiter responses are delivered in the applicant account and by email.
BEGIN;

CREATE TABLE IF NOT EXISTS application_feedback (
  id serial PRIMARY KEY,
  application_id integer NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
  recipient_user_id integer NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  company_id integer NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  message text NOT NULL CHECK (char_length(trim(message)) BETWEEN 2 AND 2000),
  created_at timestamptz NOT NULL DEFAULT now(),
  read_at timestamptz
);

CREATE INDEX IF NOT EXISTS ix_application_feedback_recipient_created
  ON application_feedback (recipient_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_application_feedback_application
  ON application_feedback (application_id);

COMMIT;
