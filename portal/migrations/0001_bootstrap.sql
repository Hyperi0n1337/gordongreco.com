BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'portal_api') THEN
    CREATE ROLE portal_api NOLOGIN NOINHERIT NOBYPASSRLS;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'portal_worker') THEN
    CREATE ROLE portal_worker NOLOGIN NOINHERIT NOBYPASSRLS;
  END IF;
END
$$;

CREATE SCHEMA IF NOT EXISTS portal;
REVOKE ALL ON SCHEMA portal FROM PUBLIC;
GRANT USAGE ON SCHEMA portal TO portal_api, portal_worker;
ALTER DEFAULT PRIVILEGES IN SCHEMA portal REVOKE ALL ON TABLES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA portal REVOKE ALL ON FUNCTIONS FROM PUBLIC;
ALTER DEFAULT PRIVILEGES IN SCHEMA portal REVOKE ALL ON SEQUENCES FROM PUBLIC;

CREATE TYPE portal.portal_role AS ENUM ('client', 'advisor', 'operations');
CREATE TYPE portal.document_state AS ENUM (
  'missing','uploading','quarantined','scanning','ready_for_review','accepted',
  'needs_replacement','duplicate','rejected','delete_pending','deleted'
);
CREATE TYPE portal.upload_state AS ENUM (
  'initializing','open','object_complete','scan_queued','complete','aborted','expired'
);
CREATE TYPE portal.policy_state AS ENUM ('draft','pending_approval','approved','rejected','superseded');
CREATE TYPE portal.cash_operation_state AS ENUM ('pending_approval','approved_for_intake','rejected','cancelled');

CREATE OR REPLACE FUNCTION portal.current_user_id()
RETURNS uuid LANGUAGE sql STABLE PARALLEL SAFE
AS $$ SELECT nullif(current_setting('app.user_id', true), '')::uuid $$;

CREATE OR REPLACE FUNCTION portal.current_actor_role()
RETURNS text LANGUAGE sql STABLE PARALLEL SAFE
AS $$ SELECT nullif(current_setting('app.actor_role', true), '') $$;

CREATE OR REPLACE FUNCTION portal.current_session_id()
RETURNS uuid LANGUAGE sql STABLE PARALLEL SAFE
AS $$ SELECT nullif(current_setting('app.session_id', true), '')::uuid $$;

CREATE OR REPLACE FUNCTION portal.current_household_ids()
RETURNS uuid[] LANGUAGE sql STABLE PARALLEL SAFE
AS $$
  SELECT CASE
    WHEN nullif(current_setting('app.household_ids', true), '') IS NULL THEN ARRAY[]::uuid[]
    ELSE string_to_array(current_setting('app.household_ids', true), ',')::uuid[]
  END
$$;

CREATE OR REPLACE FUNCTION portal.current_entity_ids()
RETURNS uuid[] LANGUAGE sql STABLE PARALLEL SAFE
AS $$
  SELECT CASE
    WHEN nullif(current_setting('app.entity_ids', true), '') IS NULL THEN ARRAY[]::uuid[]
    ELSE string_to_array(current_setting('app.entity_ids', true), ',')::uuid[]
  END
$$;

CREATE OR REPLACE FUNCTION portal.current_entity_scope()
RETURNS text[] LANGUAGE sql STABLE PARALLEL SAFE
AS $$
  SELECT CASE
    WHEN nullif(current_setting('app.entity_scope', true), '') IS NULL THEN ARRAY[]::text[]
    ELSE string_to_array(current_setting('app.entity_scope', true), ',')::text[]
  END
$$;

CREATE OR REPLACE FUNCTION portal.can_household(p_household_id uuid)
RETURNS boolean LANGUAGE sql STABLE PARALLEL SAFE
AS $$ SELECT p_household_id = ANY(portal.current_household_ids()) $$;

CREATE OR REPLACE FUNCTION portal.can_entity(p_household_id uuid, p_entity_id uuid)
RETURNS boolean LANGUAGE sql STABLE PARALLEL SAFE
AS $$
  SELECT portal.can_household(p_household_id)
     AND (
       p_entity_id IS NULL
       OR (p_household_id::text || ':' || p_entity_id::text) = ANY(portal.current_entity_scope())
     )
$$;

COMMIT;
