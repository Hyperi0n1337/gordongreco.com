BEGIN;

CREATE TABLE portal.households (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  display_label text NOT NULL CHECK (length(display_label) BETWEEN 1 AND 160),
  created_at timestamptz NOT NULL DEFAULT now(),
  archived_at timestamptz
);

CREATE TABLE portal.entities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  household_id uuid NOT NULL REFERENCES portal.households(id) ON DELETE RESTRICT,
  display_label text NOT NULL CHECK (length(display_label) BETWEEN 1 AND 160),
  entity_kind text NOT NULL CHECK (entity_kind IN ('individual','joint','trust','business','estate','other')),
  created_at timestamptz NOT NULL DEFAULT now(),
  archived_at timestamptz,
  UNIQUE (household_id, id)
);

CREATE TABLE portal.users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email citext NOT NULL UNIQUE CHECK (length(email::text) <= 254),
  display_name text NOT NULL CHECK (length(display_name) BETWEEN 1 AND 120),
  active boolean NOT NULL DEFAULT false,
  auth_epoch bigint NOT NULL DEFAULT 0 CHECK (auth_epoch >= 0),
  totp_ciphertext text,
  totp_confirmed_at timestamptz,
  totp_last_counter bigint NOT NULL DEFAULT -1,
  created_at timestamptz NOT NULL DEFAULT now(),
  revoked_at timestamptz
);

CREATE TABLE portal.memberships (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES portal.users(id) ON DELETE RESTRICT,
  household_id uuid NOT NULL REFERENCES portal.households(id) ON DELETE RESTRICT,
  role portal.portal_role NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  revoked_at timestamptz
);

CREATE UNIQUE INDEX memberships_one_active_idx
ON portal.memberships(user_id, household_id) WHERE revoked_at IS NULL;

CREATE TABLE portal.membership_entities (
  membership_id uuid NOT NULL REFERENCES portal.memberships(id) ON DELETE CASCADE,
  entity_id uuid NOT NULL REFERENCES portal.entities(id) ON DELETE RESTRICT,
  PRIMARY KEY (membership_id, entity_id)
);

CREATE TABLE portal.invitations (
  id uuid PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES portal.users(id) ON DELETE RESTRICT,
  household_id uuid NOT NULL REFERENCES portal.households(id) ON DELETE RESTRICT,
  token_digest char(64) NOT NULL UNIQUE CHECK (token_digest ~ '^[0-9a-f]{64}$'),
  created_by uuid NOT NULL REFERENCES portal.users(id) ON DELETE RESTRICT,
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL,
  consumed_at timestamptz,
  revoked_at timestamptz,
  CHECK (expires_at > created_at)
);

CREATE TABLE portal.magic_links (
  id uuid PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES portal.users(id) ON DELETE RESTRICT,
  token_digest char(64) NOT NULL UNIQUE CHECK (token_digest ~ '^[0-9a-f]{64}$'),
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL,
  consumed_at timestamptz,
  revoked_at timestamptz,
  CHECK (expires_at > created_at)
);

CREATE TABLE portal.sessions (
  id uuid PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES portal.users(id) ON DELETE RESTRICT,
  token_digest char(64) NOT NULL UNIQUE CHECK (token_digest ~ '^[0-9a-f]{64}$'),
  auth_epoch bigint NOT NULL,
  auth_level smallint NOT NULL DEFAULT 1 CHECK (auth_level IN (1,2)),
  step_up_until timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL,
  last_seen_at timestamptz,
  revoked_at timestamptz,
  CHECK (expires_at > created_at)
);

CREATE TABLE portal.recovery_codes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES portal.users(id) ON DELETE CASCADE,
  code_digest char(64) NOT NULL CHECK (code_digest ~ '^[0-9a-f]{64}$'),
  created_at timestamptz NOT NULL DEFAULT now(),
  consumed_at timestamptz,
  revoked_at timestamptz,
  UNIQUE (user_id, code_digest)
);

CREATE TABLE portal.auth_rate_limits (
  bucket_key char(64) PRIMARY KEY,
  window_started_at timestamptz NOT NULL,
  counter integer NOT NULL CHECK (counter >= 0)
);

CREATE TABLE portal.outbox (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  channel text NOT NULL CHECK (channel IN ('email','telegram','mas_intake','advisor_queue','worker')),
  topic text NOT NULL CHECK (length(topic) BETWEEN 1 AND 160),
  aggregate_id uuid NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(payload) = 'object'),
  secret_ciphertext text,
  created_at timestamptz NOT NULL DEFAULT now(),
  available_at timestamptz NOT NULL DEFAULT now(),
  claimed_at timestamptz,
  delivered_at timestamptz,
  attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  last_error text,
  UNIQUE (channel, topic, aggregate_id)
);

CREATE TABLE portal.audit_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  occurred_at timestamptz NOT NULL DEFAULT now(),
  actor_user_id uuid,
  actor_role text NOT NULL,
  action text NOT NULL,
  object_type text NOT NULL,
  object_id uuid,
  household_id uuid,
  detail jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(detail) = 'object')
);

CREATE INDEX memberships_user_active_idx ON portal.memberships(user_id, household_id) WHERE revoked_at IS NULL;
CREATE INDEX sessions_active_digest_idx ON portal.sessions(token_digest, expires_at) WHERE revoked_at IS NULL;
CREATE INDEX invitations_user_active_idx ON portal.invitations(user_id, expires_at) WHERE consumed_at IS NULL AND revoked_at IS NULL;
CREATE INDEX magic_links_user_active_idx ON portal.magic_links(user_id, expires_at) WHERE consumed_at IS NULL AND revoked_at IS NULL;
CREATE INDEX outbox_pending_idx ON portal.outbox(available_at, created_at) WHERE delivered_at IS NULL;
CREATE INDEX audit_household_time_idx ON portal.audit_events(household_id, occurred_at DESC);

CREATE OR REPLACE FUNCTION portal.authenticate_session(p_token_digest text)
RETURNS TABLE (
  user_id uuid,
  actor_role text,
  household_ids uuid[],
  entity_ids uuid[],
  entity_scope text[],
  session_id uuid,
  auth_level smallint,
  step_up_until timestamptz
)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
DECLARE
  v_session portal.sessions%ROWTYPE;
  v_user portal.users%ROWTYPE;
BEGIN
  SELECT * INTO v_session
  FROM portal.sessions s
  WHERE s.token_digest = p_token_digest
    AND s.revoked_at IS NULL
    AND s.expires_at > clock_timestamp()
  FOR UPDATE;
  IF NOT FOUND THEN RETURN; END IF;

  SELECT * INTO v_user FROM portal.users u WHERE u.id = v_session.user_id FOR SHARE;
  IF NOT FOUND OR NOT v_user.active OR v_user.revoked_at IS NOT NULL OR v_user.auth_epoch <> v_session.auth_epoch THEN
    UPDATE portal.sessions SET revoked_at = clock_timestamp() WHERE id = v_session.id;
    RETURN;
  END IF;

  UPDATE portal.sessions SET last_seen_at = clock_timestamp() WHERE id = v_session.id;
  RETURN QUERY
  WITH active_memberships AS (
    SELECT m.* FROM portal.memberships m
    WHERE m.user_id = v_user.id AND m.revoked_at IS NULL
  )
  SELECT
    v_user.id,
    CASE
      WHEN bool_or(am.role = 'advisor') THEN 'advisor'
      WHEN bool_or(am.role = 'operations') THEN 'operations'
      ELSE 'client'
    END,
    array_agg(DISTINCT am.household_id),
    COALESCE(array_agg(DISTINCT me.entity_id) FILTER (WHERE me.entity_id IS NOT NULL), ARRAY[]::uuid[]),
    COALESCE(
      array_agg(DISTINCT am.household_id::text || ':' || me.entity_id::text)
        FILTER (WHERE me.entity_id IS NOT NULL),
      ARRAY[]::text[]
    ),
    v_session.id,
    CASE WHEN v_session.step_up_until > clock_timestamp() THEN v_session.auth_level ELSE 1 END::smallint,
    v_session.step_up_until
  FROM active_memberships am
  LEFT JOIN portal.membership_entities me ON me.membership_id = am.id
  HAVING count(*) > 0;
END
$$;

CREATE OR REPLACE FUNCTION portal.consume_auth_rate_limit(p_key text, p_limit integer, p_window_seconds integer)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
DECLARE v_hash char(64) := encode(digest(p_key, 'sha256'), 'hex'); v_row portal.auth_rate_limits%ROWTYPE;
BEGIN
  IF p_limit < 1 OR p_window_seconds < 1 THEN RAISE EXCEPTION 'invalid rate limit'; END IF;
  SELECT * INTO v_row FROM portal.auth_rate_limits WHERE bucket_key = v_hash FOR UPDATE;
  IF NOT FOUND OR v_row.window_started_at + make_interval(secs => p_window_seconds) <= clock_timestamp() THEN
    INSERT INTO portal.auth_rate_limits(bucket_key, window_started_at, counter)
    VALUES (v_hash, clock_timestamp(), 1)
    ON CONFLICT (bucket_key) DO UPDATE SET window_started_at = EXCLUDED.window_started_at, counter = 1;
    RETURN;
  END IF;
  IF v_row.counter >= p_limit THEN RAISE EXCEPTION 'rate_limited' USING ERRCODE = 'P0001'; END IF;
  UPDATE portal.auth_rate_limits SET counter = counter + 1 WHERE bucket_key = v_hash;
END
$$;

REVOKE ALL ON FUNCTION portal.authenticate_session(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.consume_auth_rate_limit(text,integer,integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION portal.authenticate_session(text) TO portal_api;
GRANT EXECUTE ON FUNCTION portal.consume_auth_rate_limit(text,integer,integer) TO portal_api;

COMMIT;
