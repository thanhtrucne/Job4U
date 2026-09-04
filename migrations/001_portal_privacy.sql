-- Smart Job Portal: structured profiles, consent, wallet, partner applications.
-- Run once with the least-privileged migration role:
--   psql "$DATABASE_URL_SYNC" -f migrations/001_portal_privacy.sql
-- The application must connect with sslmode=require in production.

BEGIN;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

ALTER TABLE companies ADD COLUMN IF NOT EXISTS is_partner boolean NOT NULL DEFAULT false;
ALTER TABLE users ADD COLUMN IF NOT EXISTS company_id integer REFERENCES companies(id) ON DELETE SET NULL;
-- Demo partners for the full application flow. Create their user accounts through /api/auth/register,
-- then assign role='partner' and the corresponding company_id with the admin migration account.
INSERT INTO companies (name, slug, is_partner) VALUES
  ('Công ty Demo Sài Gòn', 'cong-ty-demo-sai-gon', true),
  ('Trung tâm Công nghệ Thành phố', 'trung-tam-cong-nghe-thanh-pho', true),
  ('Giải pháp Việc làm Việt', 'giai-phap-viec-lam-viet', true)
ON CONFLICT (name) DO UPDATE SET is_partner = true;

DO $$ BEGIN CREATE TYPE document_type AS ENUM ('personal_profile','job_application','health_certificate','qualification','identity_card'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE document_status AS ENUM ('pending','verified','rejected','expired'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE consent_purpose AS ENUM ('create_profile','job_recommend','reuse_documents','share_with_company'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE application_status AS ENUM ('pending','accepted','rejected','withdrawn'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE share_request_status AS ENUM ('pending','granted','declined','cancelled'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE job_skill_importance AS ENUM ('required','preferred'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS digital_profiles (
  id serial PRIMARY KEY, user_id integer NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
  headline varchar(255), industry varchar(255), desired_location varchar(255),
  desired_salary_min double precision, desired_salary_max double precision,
  years_experience double precision NOT NULL DEFAULT 0, education varchar(255), summary text,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz
);
CREATE TABLE IF NOT EXISTS profile_skills (
  id serial PRIMARY KEY, profile_id integer NOT NULL REFERENCES digital_profiles(id) ON DELETE CASCADE,
  skill_id integer NOT NULL REFERENCES skills(id) ON DELETE RESTRICT, proficiency integer,
  CONSTRAINT uq_profile_skills UNIQUE(profile_id, skill_id),
  CONSTRAINT ck_profile_skill_proficiency CHECK (proficiency IS NULL OR proficiency BETWEEN 1 AND 5)
);
CREATE TABLE IF NOT EXISTS job_skill_requirements (
  id serial PRIMARY KEY, job_id integer NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  skill_id integer NOT NULL REFERENCES skills(id) ON DELETE RESTRICT,
  importance job_skill_importance NOT NULL DEFAULT 'required', tfidf_weight double precision NOT NULL DEFAULT 1,
  CONSTRAINT uq_job_skill_requirements UNIQUE(job_id, skill_id)
);
CREATE TABLE IF NOT EXISTS documents (
  id serial PRIMARY KEY, user_id integer NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  doc_type document_type NOT NULL, file_path text NOT NULL, status document_status NOT NULL DEFAULT 'pending',
  is_sensitive boolean NOT NULL DEFAULT false, sensitive_metadata_encrypted text,
  expiry_date date, rejection_reason text, verified_by integer REFERENCES users(id) ON DELETE SET NULL,
  verified_at timestamptz, uploaded_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS consents (
  id serial PRIMARY KEY, user_id integer NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  purpose consent_purpose NOT NULL, granted_at timestamptz, revoked_at timestamptz,
  consent_text_version varchar(50) NOT NULL,
  CONSTRAINT uq_consents_user_purpose UNIQUE(user_id, purpose)
);
CREATE TABLE IF NOT EXISTS applications (
  id serial PRIMARY KEY, user_id integer NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  job_id integer NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  company_id integer NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  status application_status NOT NULL DEFAULT 'pending', created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz,
  CONSTRAINT uq_application_user_job UNIQUE(user_id, job_id)
);
CREATE TABLE IF NOT EXISTS application_share_requests (
  id serial PRIMARY KEY, application_id integer NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
  company_id integer NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  requested_doc_types varchar[] NOT NULL DEFAULT '{}', status share_request_status NOT NULL DEFAULT 'pending',
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS share_consent_logs (
  id serial PRIMARY KEY, share_request_id integer NOT NULL REFERENCES application_share_requests(id) ON DELETE CASCADE,
  user_id integer NOT NULL REFERENCES users(id) ON DELETE CASCADE, granted_at timestamptz NOT NULL DEFAULT now(),
  data_shared_snapshot jsonb NOT NULL, ip_address varchar(64)
);
CREATE INDEX IF NOT EXISTS ix_documents_user_id ON documents(user_id);
CREATE INDEX IF NOT EXISTS ix_documents_pending ON documents(status) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS ix_share_consent_logs_user_id ON share_consent_logs(user_id);

-- Sensitive fields are encrypted with a key supplied only by the admin verification session:
-- UPDATE documents SET sensitive_metadata_encrypted = pgp_sym_encrypt(:value, current_setting('app.encryption_key')) ...
-- Do not put the key in source code or the normal application connection string.

-- RLS guarantees a user can see only records tagged with its session user id.
-- Before each user-scoped query, set `SET LOCAL app.user_id = '<id>'` in the transaction.
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS documents_owner_policy ON documents;
CREATE POLICY documents_owner_policy ON documents
  USING (user_id = NULLIF(current_setting('app.user_id', true), '')::integer)
  WITH CHECK (user_id = NULLIF(current_setting('app.user_id', true), '')::integer);
ALTER TABLE share_consent_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE share_consent_logs FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS share_logs_owner_policy ON share_consent_logs;
CREATE POLICY share_logs_owner_policy ON share_consent_logs
  USING (user_id = NULLIF(current_setting('app.user_id', true), '')::integer)
  WITH CHECK (user_id = NULLIF(current_setting('app.user_id', true), '')::integer);

-- Create these roles manually with passwords/secrets supplied by the deployer.
-- GRANT admin_verify_docs to the DB account used only by the document-review worker.
DO $$ BEGIN CREATE ROLE app_runtime NOINHERIT; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE ROLE admin_verify_docs NOINHERIT; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE ROLE reporting_reader NOINHERIT; EXCEPTION WHEN duplicate_object THEN NULL; END $$;
GRANT SELECT, INSERT, UPDATE ON documents, share_consent_logs TO app_runtime;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_runtime;
GRANT SELECT, INSERT, UPDATE ON documents, share_consent_logs TO admin_verify_docs;
GRANT SELECT ON jobs, companies, categories TO reporting_reader;
-- The admin role is deliberately granted its own explicit policy, not a superuser bypass.
DROP POLICY IF EXISTS documents_admin_policy ON documents;
CREATE POLICY documents_admin_policy ON documents TO admin_verify_docs USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS share_logs_admin_policy ON share_consent_logs;
CREATE POLICY share_logs_admin_policy ON share_consent_logs TO admin_verify_docs USING (true) WITH CHECK (true);
COMMIT;
