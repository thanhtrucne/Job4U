-- Repair a legacy lossy-encoding value found in candidate profile locations.
-- The replacement is deliberately exact: it does not alter unrelated user data.
BEGIN;

UPDATE candidate_profiles
SET province = 'Hồ Chí Minh'
WHERE province IN ('H? Ch? Minh', 'TP H? Ch? Minh');

COMMIT;
