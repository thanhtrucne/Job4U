-- Applicant dashboard profile. Identity numbers are stored encrypted by the API.
BEGIN;
CREATE TABLE IF NOT EXISTS candidate_profiles (
  id serial PRIMARY KEY,
  user_id integer NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
  nationality varchar(100), date_of_birth date, gender varchar(30), place_of_birth varchar(255),
  marital_status varchar(50), height_cm double precision, weight_kg double precision, driving_license_type varchar(50),
  contact_address text, province varchar(100), ward varchar(100),
  education_level varchar(100), education_grade varchar(100), specialization varchar(255), training_institution varchar(255),
  foreign_language varchar(255), foreign_language_school varchar(255), computer_skill varchar(255), computer_school varchar(255),
  years_experience double precision, work_experience text, workplace varchar(255),
  identity_document_number_encrypted text, identity_issue_date date, identity_issue_place varchar(255),
  religion varchar(100), ethnicity varchar(100), employment_status varchar(50), notes text,
  created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz,
  CONSTRAINT ck_candidate_profile_status CHECK (employment_status IS NULL OR employment_status IN ('seeking', 'employed', 'paused'))
);
CREATE INDEX IF NOT EXISTS ix_candidate_profiles_user_id ON candidate_profiles(user_id);
COMMIT;
