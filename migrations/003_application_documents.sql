-- Bind each uploaded application file to one specific job application.
-- This prevents a company from seeing a file submitted to a different company.
BEGIN;
CREATE TABLE IF NOT EXISTS application_documents (
  id serial PRIMARY KEY,
  application_id integer NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
  document_id integer NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  CONSTRAINT uq_application_documents UNIQUE(application_id, document_id)
);
CREATE INDEX IF NOT EXISTS ix_application_documents_application_id ON application_documents(application_id);
CREATE INDEX IF NOT EXISTS ix_application_documents_document_id ON application_documents(document_id);
COMMIT;
