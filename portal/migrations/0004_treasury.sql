BEGIN;

CREATE TABLE portal.treasury_policy_versions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  household_id uuid NOT NULL REFERENCES portal.households(id) ON DELETE RESTRICT,
  version integer NOT NULL CHECK (version >= 1),
  base_version_id uuid REFERENCES portal.treasury_policy_versions(id) ON DELETE RESTRICT,
  effective_at timestamptz NOT NULL,
  terms jsonb NOT NULL CHECK (
    jsonb_typeof(terms) = 'object'
    AND terms ?& ARRAY['currency','minimum_operating_reserve_minor','cash_operation_limit_minor','permitted_operation_types']
    AND jsonb_typeof(terms->'permitted_operation_types') = 'array'
  ),
  signer_user_ids uuid[] NOT NULL CHECK (cardinality(signer_user_ids) BETWEEN 1 AND 20),
  approval_threshold integer NOT NULL CHECK (approval_threshold >= 1 AND approval_threshold <= cardinality(signer_user_ids)),
  state portal.policy_state NOT NULL DEFAULT 'pending_approval',
  created_by uuid NOT NULL REFERENCES portal.users(id) ON DELETE RESTRICT,
  created_at timestamptz NOT NULL DEFAULT now(),
  approved_at timestamptz,
  revision integer NOT NULL DEFAULT 1 CHECK (revision >= 1),
  idempotency_key text NOT NULL CHECK (idempotency_key ~ '^[A-Za-z0-9._:-]{8,128}$'),
  UNIQUE (household_id, version),
  UNIQUE (household_id, idempotency_key),
  UNIQUE (household_id, effective_at),
  CHECK (base_version_id IS NOT NULL OR version = 1),
  CHECK (effective_at > created_at),
  CHECK ((state = 'approved') = (approved_at IS NOT NULL) OR state = 'superseded')
);

CREATE UNIQUE INDEX treasury_one_pending_base_idx
ON portal.treasury_policy_versions(household_id, base_version_id)
WHERE state = 'pending_approval';

CREATE TABLE portal.cash_operations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  household_id uuid NOT NULL REFERENCES portal.households(id) ON DELETE RESTRICT,
  entity_id uuid,
  policy_version_id uuid NOT NULL REFERENCES portal.treasury_policy_versions(id) ON DELETE RESTRICT,
  operation_type text NOT NULL CHECK (operation_type IN (
    'operating_reserve_adjustment','planned_tax_payment_reserve',
    'same_entity_liquidity_allocation','external_cash_need_notice'
  )),
  amount_minor bigint NOT NULL CHECK (amount_minor > 0),
  currency char(3) NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
  requested_effective_at timestamptz NOT NULL,
  rationale text NOT NULL CHECK (length(rationale) BETWEEN 1 AND 2000),
  conflict_key text NOT NULL CHECK (length(conflict_key) BETWEEN 1 AND 160),
  signer_user_ids uuid[] NOT NULL CHECK (cardinality(signer_user_ids) BETWEEN 1 AND 20),
  approval_threshold integer NOT NULL CHECK (approval_threshold >= 1 AND approval_threshold <= cardinality(signer_user_ids)),
  state portal.cash_operation_state NOT NULL DEFAULT 'pending_approval',
  created_by uuid NOT NULL REFERENCES portal.users(id) ON DELETE RESTRICT,
  created_at timestamptz NOT NULL DEFAULT now(),
  idempotency_key text NOT NULL CHECK (idempotency_key ~ '^[A-Za-z0-9._:-]{8,128}$'),
  revision integer NOT NULL DEFAULT 1 CHECK (revision >= 1),
  approved_at timestamptz,
  execution_state text NOT NULL DEFAULT 'not_executable' CHECK (execution_state = 'not_executable'),
  UNIQUE (household_id, idempotency_key),
  CHECK (requested_effective_at >= created_at),
  CONSTRAINT cash_operations_entity_scope_fk FOREIGN KEY (household_id, entity_id)
    REFERENCES portal.entities(household_id, id) ON DELETE RESTRICT
);

CREATE UNIQUE INDEX cash_operation_conflict_idx
ON portal.cash_operations(household_id, conflict_key)
WHERE state IN ('pending_approval','approved_for_intake');

CREATE TABLE portal.workflow_approvals (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workflow_type text NOT NULL CHECK (workflow_type IN ('treasury_policy','cash_operation')),
  workflow_id uuid NOT NULL,
  signer_user_id uuid NOT NULL REFERENCES portal.users(id) ON DELETE RESTRICT,
  workflow_revision integer NOT NULL CHECK (workflow_revision >= 1),
  approved_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (workflow_type, workflow_id, signer_user_id)
);

CREATE TABLE portal.recalculation_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  household_id uuid NOT NULL REFERENCES portal.households(id) ON DELETE RESTRICT,
  reason text NOT NULL CHECK (reason IN ('treasury_policy_version_approved','cash_operation_approved_for_intake')),
  source_id uuid NOT NULL,
  requested_at timestamptz NOT NULL DEFAULT now(),
  available_at timestamptz NOT NULL DEFAULT now(),
  claimed_at timestamptz,
  completed_at timestamptz,
  attempts integer NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 20),
  last_error text,
  UNIQUE (reason, source_id)
);

CREATE INDEX policy_scope_version_idx ON portal.treasury_policy_versions(household_id, version DESC);
CREATE INDEX policy_effective_idx ON portal.treasury_policy_versions(household_id, effective_at DESC) WHERE state IN ('approved','superseded');
CREATE INDEX cash_scope_state_idx ON portal.cash_operations(household_id, state, created_at DESC);
CREATE INDEX approvals_workflow_idx ON portal.workflow_approvals(workflow_type, workflow_id);
CREATE INDEX recalculation_pending_idx ON portal.recalculation_jobs(available_at) WHERE completed_at IS NULL;

COMMIT;
