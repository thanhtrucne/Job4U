-- Each account must have a unique, canonical phone number.
-- Run after 004_candidate_dashboard.sql.
BEGIN;

-- Remove display formatting first, so equivalent numbers cannot coexist.
UPDATE users
SET phone_number = regexp_replace(phone_number, '[^0-9]', '', 'g')
WHERE phone_number IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_users_phone_number
ON users(phone_number)
WHERE phone_number IS NOT NULL;

COMMIT;
