BEGIN;

CREATE TABLE portal.document_requests (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  household_id uuid NOT NULL REFERENCES portal.households(id) ON DELETE RESTRICT,
  entity_id uuid,
  title text NOT NULL CHECK (length(title) BETWEEN 1 AND 160),
  description text NOT NULL DEFAULT '' CHECK (length(description) <= 2000),
  due_at timestamptz,
  status text NOT NULL DEFAULT 'missing' CHECK (status IN ('missing','uploading','quarantined','review','complete','closed')),
  created_by uuid NOT NULL REFERENCES portal.users(id) ON DELETE RESTRICT,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  CONSTRAINT document_requests_entity_scope_fk FOREIGN KEY (household_id, entity_id)
    REFERENCES portal.entities(household_id, id) ON DELETE RESTRICT
);

CREATE TABLE portal.documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  household_id uuid NOT NULL REFERENCES portal.households(id) ON DELETE RESTRICT,
  entity_id uuid,
  request_id uuid NOT NULL REFERENCES portal.document_requests(id) ON DELETE RESTRICT,
  uploaded_by uuid NOT NULL REFERENCES portal.users(id) ON DELETE RESTRICT,
  original_filename text NOT NULL CHECK (length(original_filename) BETWEEN 1 AND 180 AND original_filename !~ '[\\/[:cntrl:]]'),
  declared_content_type text NOT NULL CHECK (declared_content_type IN ('application/pdf','image/jpeg','image/png','text/plain','text/csv','application/csv')),
  authoritative_content_type text,
  authoritative_size bigint CHECK (authoritative_size BETWEEN 1 AND 26214400),
  authoritative_sha256 char(64) CHECK (authoritative_sha256 IS NULL OR authoritative_sha256 ~ '^[0-9a-f]{64}$'),
  quarantine_key text NOT NULL UNIQUE CHECK (
    quarantine_key ~ '^quarantine/[0-9a-f-]{36}/[0-9a-f-]{36}/[0-9a-f-]{36}$'
  ),
  clean_key text UNIQUE CHECK (
    clean_key IS NULL OR clean_key ~ '^clean/[0-9a-f-]{36}/[0-9a-f-]{36}/[0-9a-f-]{36}$'
  ),
  state portal.document_state NOT NULL DEFAULT 'uploading',
  duplicate_of uuid REFERENCES portal.documents(id) ON DELETE RESTRICT,
  review_note text CHECK (length(review_note) <= 1000),
  revision integer NOT NULL DEFAULT 1 CHECK (revision >= 1),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  deleted_at timestamptz,
  CONSTRAINT documents_entity_scope_fk FOREIGN KEY (household_id, entity_id)
    REFERENCES portal.entities(household_id, id) ON DELETE RESTRICT,
  CHECK ((state IN ('ready_for_review','accepted') AND clean_key IS NOT NULL) OR state NOT IN ('ready_for_review','accepted')),
  CHECK ((authoritative_sha256 IS NULL) = (authoritative_size IS NULL))
);

CREATE TABLE portal.uploads (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id uuid NOT NULL UNIQUE REFERENCES portal.documents(id) ON DELETE RESTRICT,
  household_id uuid NOT NULL REFERENCES portal.households(id) ON DELETE RESTRICT,
  object_key text NOT NULL UNIQUE,
  declared_size bigint NOT NULL CHECK (declared_size BETWEEN 1 AND 26214400),
  multipart_upload_id text,
  idempotency_key text NOT NULL CHECK (idempotency_key ~ '^[A-Za-z0-9._:-]{8,128}$'),
  state portal.upload_state NOT NULL DEFAULT 'initializing',
  uploaded_bytes bigint NOT NULL DEFAULT 0 CHECK (uploaded_bytes >= 0 AND uploaded_bytes <= 26214400),
  created_by uuid NOT NULL REFERENCES portal.users(id) ON DELETE RESTRICT,
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL DEFAULT (now() + interval '2 hours'),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (created_by, idempotency_key),
  CHECK (expires_at > created_at)
);

CREATE TABLE portal.upload_parts (
  upload_id uuid NOT NULL REFERENCES portal.uploads(id) ON DELETE CASCADE,
  part_number integer NOT NULL CHECK (part_number BETWEEN 1 AND 10000),
  etag text NOT NULL CHECK (length(etag) BETWEEN 1 AND 200),
  size_bytes integer NOT NULL CHECK (size_bytes BETWEEN 1 AND 8388608),
  recorded_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (upload_id, part_number)
);

CREATE TABLE portal.scan_jobs (
  document_id uuid PRIMARY KEY REFERENCES portal.documents(id) ON DELETE CASCADE,
  available_at timestamptz NOT NULL DEFAULT now(),
  claimed_at timestamptz,
  claimed_by text,
  attempts integer NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 20),
  last_error text,
  completed_at timestamptz
);

CREATE TABLE portal.object_delete_jobs (
  document_id uuid PRIMARY KEY REFERENCES portal.documents(id) ON DELETE CASCADE,
  final_state portal.document_state NOT NULL DEFAULT 'deleted' CHECK (final_state IN ('duplicate','deleted')),
  available_at timestamptz NOT NULL DEFAULT now(),
  claimed_at timestamptz,
  claimed_by text,
  attempts integer NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 20),
  last_error text,
  completed_at timestamptz
);

CREATE TABLE portal.immutable_receipts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  household_id uuid NOT NULL REFERENCES portal.households(id) ON DELETE RESTRICT,
  document_id uuid REFERENCES portal.documents(id) ON DELETE RESTRICT,
  event_type text NOT NULL CHECK (length(event_type) BETWEEN 1 AND 160),
  event_at timestamptz NOT NULL DEFAULT now(),
  actor_id text NOT NULL CHECK (length(actor_id) BETWEEN 1 AND 160),
  payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
  receipt_sha256 char(64) NOT NULL UNIQUE CHECK (receipt_sha256 ~ '^[0-9a-f]{64}$')
);

CREATE TABLE portal.support_requests (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  household_id uuid NOT NULL REFERENCES portal.households(id) ON DELETE RESTRICT,
  created_by uuid NOT NULL REFERENCES portal.users(id) ON DELETE RESTRICT,
  category text NOT NULL DEFAULT 'portal_document_support' CHECK (category = 'portal_document_support'),
  message text NOT NULL CHECK (length(message) BETWEEN 1 AND 500),
  status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','acknowledged','closed')),
  created_at timestamptz NOT NULL DEFAULT now(),
  closed_at timestamptz
);

CREATE INDEX document_requests_scope_idx ON portal.document_requests(household_id, entity_id, status, due_at) WHERE deleted_at IS NULL;
CREATE INDEX documents_scope_state_idx ON portal.documents(household_id, entity_id, state, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX documents_hash_idx ON portal.documents(household_id, authoritative_sha256, authoritative_size) WHERE authoritative_sha256 IS NOT NULL;
CREATE UNIQUE INDEX documents_one_clean_hash_idx ON portal.documents(household_id, authoritative_sha256, authoritative_size)
  WHERE state IN ('ready_for_review','accepted') AND deleted_at IS NULL;
CREATE INDEX uploads_open_idx ON portal.uploads(expires_at) WHERE state IN ('initializing','open');
CREATE INDEX scan_jobs_ready_idx ON portal.scan_jobs(available_at) WHERE completed_at IS NULL;
CREATE INDEX delete_jobs_ready_idx ON portal.object_delete_jobs(available_at) WHERE completed_at IS NULL;
CREATE INDEX receipts_scope_time_idx ON portal.immutable_receipts(household_id, event_at DESC);
CREATE INDEX support_scope_time_idx ON portal.support_requests(household_id, created_at DESC);

COMMIT;
