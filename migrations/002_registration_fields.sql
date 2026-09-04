-- Account registration fields. Safe to run once after 001_portal_privacy.sql.
BEGIN;
ALTER TABLE users ADD COLUMN IF NOT EXISTS phone_number varchar(32);
ALTER TABLE users ADD COLUMN IF NOT EXISTS data_policy_accepted_at timestamptz;
ALTER TABLE users ADD COLUMN IF NOT EXISTS data_policy_version varchar(50);
CREATE INDEX IF NOT EXISTS ix_users_phone_number ON users(phone_number);
COMMIT;
