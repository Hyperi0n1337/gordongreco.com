BEGIN;

CREATE OR REPLACE FUNCTION portal.has_household_role(p_household_id uuid, p_roles portal.portal_role[])
RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM portal.memberships m
    WHERE m.user_id = portal.current_user_id()
      AND m.household_id = p_household_id
      AND m.revoked_at IS NULL
      AND m.role = ANY(p_roles)
  )
$$;

CREATE OR REPLACE FUNCTION portal.can_view_user(p_user_id uuid)
RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
  SELECT p_user_id = portal.current_user_id()
     OR EXISTS (
       SELECT 1
       FROM portal.memberships target
       JOIN portal.memberships actor ON actor.household_id = target.household_id
       WHERE target.user_id = p_user_id
         AND target.revoked_at IS NULL
         AND actor.user_id = portal.current_user_id()
         AND actor.revoked_at IS NULL
         AND actor.role IN ('advisor','operations')
     )
$$;

CREATE OR REPLACE FUNCTION portal.has_current_step_up()
RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
  SELECT EXISTS (
    SELECT 1 FROM portal.sessions s
    JOIN portal.users u ON u.id = s.user_id
    WHERE s.id = portal.current_session_id()
      AND s.user_id = portal.current_user_id()
      AND s.revoked_at IS NULL
      AND s.expires_at > clock_timestamp()
      AND s.auth_epoch = u.auth_epoch
      AND s.auth_level = 2
      AND s.step_up_until > clock_timestamp()
  )
$$;

ALTER TABLE portal.households ENABLE ROW LEVEL SECURITY;
ALTER TABLE portal.households FORCE ROW LEVEL SECURITY;
CREATE POLICY households_select ON portal.households FOR SELECT TO portal_api
USING (portal.can_household(id));

ALTER TABLE portal.entities ENABLE ROW LEVEL SECURITY;
ALTER TABLE portal.entities FORCE ROW LEVEL SECURITY;
CREATE POLICY entities_select ON portal.entities FOR SELECT TO portal_api
USING (portal.can_entity(household_id, id));

ALTER TABLE portal.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE portal.users FORCE ROW LEVEL SECURITY;
CREATE POLICY users_select ON portal.users FOR SELECT TO portal_api
USING (portal.can_view_user(id));

ALTER TABLE portal.memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE portal.memberships FORCE ROW LEVEL SECURITY;
CREATE POLICY memberships_select ON portal.memberships FOR SELECT TO portal_api
USING (
  user_id = portal.current_user_id()
  OR (portal.can_household(household_id) AND portal.has_household_role(household_id, ARRAY['advisor','operations']::portal.portal_role[]))
);

ALTER TABLE portal.membership_entities ENABLE ROW LEVEL SECURITY;
ALTER TABLE portal.membership_entities FORCE ROW LEVEL SECURITY;
CREATE POLICY membership_entities_select ON portal.membership_entities FOR SELECT TO portal_api
USING (
  EXISTS (
    SELECT 1 FROM portal.memberships m
    WHERE m.id = membership_id
      AND (m.user_id = portal.current_user_id()
        OR (portal.can_household(m.household_id) AND portal.has_household_role(m.household_id, ARRAY['advisor','operations']::portal.portal_role[])))
  )
);

ALTER TABLE portal.invitations ENABLE ROW LEVEL SECURITY;
ALTER TABLE portal.invitations FORCE ROW LEVEL SECURITY;
CREATE POLICY invitations_select ON portal.invitations FOR SELECT TO portal_api
USING (portal.has_household_role(household_id, ARRAY['advisor']::portal.portal_role[]));

ALTER TABLE portal.magic_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE portal.magic_links FORCE ROW LEVEL SECURITY;
-- No portal_api direct policy: passwordless links are RPC-only.

ALTER TABLE portal.sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE portal.sessions FORCE ROW LEVEL SECURITY;
CREATE POLICY sessions_self_select ON portal.sessions FOR SELECT TO portal_api
USING (user_id = portal.current_user_id() AND id = portal.current_session_id());

ALTER TABLE portal.recovery_codes ENABLE ROW LEVEL SECURITY;
ALTER TABLE portal.recovery_codes FORCE ROW LEVEL SECURITY;
-- Recovery codes are RPC-only and never returned after creation.

ALTER TABLE portal.auth_rate_limits ENABLE ROW LEVEL SECURITY;
ALTER TABLE portal.auth_rate_limits FORCE ROW LEVEL SECURITY;
ALTER TABLE portal.outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE portal.outbox FORCE ROW LEVEL SECURITY;
ALTER TABLE portal.audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE portal.audit_events FORCE ROW LEVEL SECURITY;
CREATE POLICY audit_select ON portal.audit_events FOR SELECT TO portal_api
USING (
  household_id IS NOT NULL
  AND portal.can_household(household_id)
  AND portal.has_household_role(household_id, ARRAY['advisor','operations']::portal.portal_role[])
);

ALTER TABLE portal.document_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE portal.document_requests FORCE ROW LEVEL SECURITY;
CREATE POLICY document_requests_select ON portal.document_requests FOR SELECT TO portal_api
USING (portal.can_entity(household_id, entity_id));

ALTER TABLE portal.documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE portal.documents FORCE ROW LEVEL SECURITY;
CREATE POLICY documents_select ON portal.documents FOR SELECT TO portal_api
USING (portal.can_entity(household_id, entity_id));

ALTER TABLE portal.uploads ENABLE ROW LEVEL SECURITY;
ALTER TABLE portal.uploads FORCE ROW LEVEL SECURITY;
CREATE POLICY uploads_select ON portal.uploads FOR SELECT TO portal_api
USING (portal.can_household(household_id) AND created_by = portal.current_user_id());

ALTER TABLE portal.upload_parts ENABLE ROW LEVEL SECURITY;
ALTER TABLE portal.upload_parts FORCE ROW LEVEL SECURITY;
CREATE POLICY upload_parts_select ON portal.upload_parts FOR SELECT TO portal_api
USING (EXISTS (
  SELECT 1 FROM portal.uploads u
  WHERE u.id = upload_id AND u.created_by = portal.current_user_id() AND portal.can_household(u.household_id)
));

ALTER TABLE portal.scan_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE portal.scan_jobs FORCE ROW LEVEL SECURITY;
ALTER TABLE portal.object_delete_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE portal.object_delete_jobs FORCE ROW LEVEL SECURITY;

ALTER TABLE portal.immutable_receipts ENABLE ROW LEVEL SECURITY;
ALTER TABLE portal.immutable_receipts FORCE ROW LEVEL SECURITY;
CREATE POLICY receipts_select ON portal.immutable_receipts FOR SELECT TO portal_api
USING (portal.can_household(household_id));

ALTER TABLE portal.support_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE portal.support_requests FORCE ROW LEVEL SECURITY;
CREATE POLICY support_select ON portal.support_requests FOR SELECT TO portal_api
USING (
  portal.can_household(household_id)
  AND (created_by = portal.current_user_id() OR portal.has_household_role(household_id, ARRAY['advisor','operations']::portal.portal_role[]))
);

ALTER TABLE portal.treasury_policy_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE portal.treasury_policy_versions FORCE ROW LEVEL SECURITY;
CREATE POLICY policy_versions_select ON portal.treasury_policy_versions FOR SELECT TO portal_api
USING (portal.can_household(household_id));

ALTER TABLE portal.cash_operations ENABLE ROW LEVEL SECURITY;
ALTER TABLE portal.cash_operations FORCE ROW LEVEL SECURITY;
CREATE POLICY cash_operations_select ON portal.cash_operations FOR SELECT TO portal_api
USING (portal.can_entity(household_id, entity_id));

ALTER TABLE portal.workflow_approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE portal.workflow_approvals FORCE ROW LEVEL SECURITY;
CREATE POLICY approvals_select ON portal.workflow_approvals FOR SELECT TO portal_api
USING (
  (workflow_type = 'treasury_policy' AND EXISTS (
    SELECT 1 FROM portal.treasury_policy_versions p WHERE p.id = workflow_id AND portal.can_household(p.household_id)
  ))
  OR
  (workflow_type = 'cash_operation' AND EXISTS (
    SELECT 1 FROM portal.cash_operations c WHERE c.id = workflow_id AND portal.can_entity(c.household_id, c.entity_id)
  ))
);

ALTER TABLE portal.recalculation_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE portal.recalculation_jobs FORCE ROW LEVEL SECURITY;

REVOKE ALL ON ALL TABLES IN SCHEMA portal FROM portal_api, portal_worker;
GRANT SELECT ON portal.households, portal.entities, portal.users, portal.memberships,
  portal.membership_entities, portal.invitations, portal.sessions, portal.audit_events,
  portal.document_requests, portal.documents, portal.uploads, portal.upload_parts,
  portal.immutable_receipts, portal.support_requests, portal.treasury_policy_versions,
  portal.cash_operations, portal.workflow_approvals
TO portal_api;

REVOKE ALL ON FUNCTION portal.has_household_role(uuid,portal.portal_role[]) FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.can_view_user(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.has_current_step_up() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION portal.has_household_role(uuid,portal.portal_role[]) TO portal_api;
GRANT EXECUTE ON FUNCTION portal.can_view_user(uuid) TO portal_api;
GRANT EXECUTE ON FUNCTION portal.has_current_step_up() TO portal_api;

COMMIT;
