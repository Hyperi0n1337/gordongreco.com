BEGIN;

CREATE OR REPLACE FUNCTION portal.write_audit(
  p_action text,
  p_object_type text,
  p_object_id uuid,
  p_household_id uuid,
  p_detail jsonb DEFAULT '{}'::jsonb,
  p_actor_id uuid DEFAULT portal.current_user_id(),
  p_actor_role text DEFAULT portal.current_actor_role()
)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
BEGIN
  INSERT INTO portal.audit_events(actor_user_id, actor_role, action, object_type, object_id, household_id, detail)
  VALUES (p_actor_id, COALESCE(p_actor_role, 'system'), p_action, p_object_type, p_object_id, p_household_id, COALESCE(p_detail, '{}'::jsonb));
END
$$;

CREATE OR REPLACE FUNCTION portal.rpc_request_magic_link(
  p_link_id uuid,
  p_email citext,
  p_token_digest text,
  p_token_ciphertext text,
  p_expires_at timestamptz
)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
DECLARE v_user portal.users%ROWTYPE; v_eligible boolean;
BEGIN
  IF p_expires_at <= clock_timestamp() OR p_expires_at > clock_timestamp() + interval '15 minutes' THEN
    RAISE EXCEPTION 'invalid link expiry';
  END IF;
  SELECT * INTO v_user FROM portal.users u WHERE u.email = p_email AND u.revoked_at IS NULL FOR UPDATE;
  IF NOT FOUND THEN RETURN false; END IF;
  SELECT EXISTS (
    SELECT 1 FROM portal.memberships m
    WHERE m.user_id = v_user.id AND m.revoked_at IS NULL
  ) AND (
    v_user.active OR EXISTS (
      SELECT 1 FROM portal.invitations i
      WHERE i.user_id = v_user.id AND i.consumed_at IS NULL AND i.revoked_at IS NULL AND i.expires_at > clock_timestamp()
    )
  ) INTO v_eligible;
  IF NOT v_eligible THEN RETURN false; END IF;
  UPDATE portal.magic_links SET revoked_at = clock_timestamp()
  WHERE user_id = v_user.id AND consumed_at IS NULL AND revoked_at IS NULL;
  INSERT INTO portal.magic_links(id, user_id, token_digest, expires_at)
  VALUES (p_link_id, v_user.id, p_token_digest, p_expires_at);
  INSERT INTO portal.outbox(channel, topic, aggregate_id, payload, secret_ciphertext)
  VALUES (
    'email','portal.magic_link',p_link_id,
    jsonb_build_object('recipient', v_user.email::text, 'template', 'passwordless_magic_link', 'token_id', p_link_id),
    p_token_ciphertext
  );
  RETURN true;
END
$$;

CREATE OR REPLACE FUNCTION portal.rpc_consume_magic_link(
  p_link_digest text,
  p_session_id uuid,
  p_session_digest text,
  p_session_expires_at timestamptz
)
RETURNS TABLE(session_id uuid, totp_enrolled boolean)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
DECLARE v_link portal.magic_links%ROWTYPE; v_user portal.users%ROWTYPE; v_invite portal.invitations%ROWTYPE;
BEGIN
  SELECT * INTO v_link FROM portal.magic_links l
  WHERE l.token_digest = p_link_digest
    AND l.consumed_at IS NULL AND l.revoked_at IS NULL AND l.expires_at > clock_timestamp()
  FOR UPDATE;
  IF NOT FOUND THEN RETURN; END IF;
  SELECT * INTO v_user FROM portal.users u WHERE u.id = v_link.user_id FOR UPDATE;
  IF NOT FOUND OR v_user.revoked_at IS NOT NULL THEN RETURN; END IF;
  IF NOT EXISTS (SELECT 1 FROM portal.memberships m WHERE m.user_id = v_user.id AND m.revoked_at IS NULL) THEN RETURN; END IF;
  IF NOT v_user.active THEN
    SELECT * INTO v_invite FROM portal.invitations i
    WHERE i.user_id = v_user.id AND i.consumed_at IS NULL AND i.revoked_at IS NULL AND i.expires_at > clock_timestamp()
    ORDER BY i.created_at DESC LIMIT 1 FOR UPDATE;
    IF NOT FOUND THEN RETURN; END IF;
    UPDATE portal.invitations SET consumed_at = clock_timestamp() WHERE id = v_invite.id;
    UPDATE portal.users SET active = true WHERE id = v_user.id;
  END IF;
  IF p_session_expires_at <= clock_timestamp() OR p_session_expires_at > clock_timestamp() + interval '13 hours' THEN
    RAISE EXCEPTION 'invalid session expiry';
  END IF;
  UPDATE portal.magic_links SET consumed_at = clock_timestamp() WHERE id = v_link.id;
  INSERT INTO portal.sessions(id,user_id,token_digest,auth_epoch,expires_at,last_seen_at)
  VALUES (p_session_id,v_user.id,p_session_digest,v_user.auth_epoch,p_session_expires_at,clock_timestamp());
  PERFORM portal.write_audit('portal.session.created','session',p_session_id,NULL,jsonb_build_object('auth_level',1),v_user.id,'client');
  RETURN QUERY SELECT p_session_id, (v_user.totp_confirmed_at IS NOT NULL);
END
$$;

CREATE OR REPLACE FUNCTION portal.rpc_consume_invitation(
  p_invitation_digest text,
  p_session_id uuid,
  p_session_digest text,
  p_session_expires_at timestamptz
)
RETURNS TABLE(session_id uuid, totp_enrolled boolean)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
DECLARE
  v_invite portal.invitations%ROWTYPE;
  v_user portal.users%ROWTYPE;
  v_role text;
BEGIN
  SELECT * INTO v_invite FROM portal.invitations i
  WHERE i.token_digest = p_invitation_digest
    AND i.consumed_at IS NULL AND i.revoked_at IS NULL AND i.expires_at > clock_timestamp()
  FOR UPDATE;
  IF NOT FOUND THEN RETURN; END IF;

  SELECT * INTO v_user FROM portal.users u WHERE u.id = v_invite.user_id FOR UPDATE;
  IF NOT FOUND OR v_user.revoked_at IS NOT NULL THEN RETURN; END IF;
  SELECT m.role::text INTO v_role FROM portal.memberships m
  WHERE m.user_id = v_user.id AND m.household_id = v_invite.household_id AND m.revoked_at IS NULL;
  IF NOT FOUND THEN RETURN; END IF;
  IF p_session_expires_at <= clock_timestamp() OR p_session_expires_at > clock_timestamp() + interval '13 hours' THEN
    RAISE EXCEPTION 'invalid session expiry';
  END IF;

  UPDATE portal.invitations SET consumed_at = clock_timestamp() WHERE id = v_invite.id;
  UPDATE portal.users SET active = true WHERE id = v_user.id;
  INSERT INTO portal.sessions(id,user_id,token_digest,auth_epoch,expires_at,last_seen_at)
  VALUES (p_session_id,v_user.id,p_session_digest,v_user.auth_epoch,p_session_expires_at,clock_timestamp());
  PERFORM portal.write_audit(
    'portal.invitation.consumed','invitation',v_invite.id,v_invite.household_id,
    jsonb_build_object('session_id',p_session_id),v_user.id,v_role
  );
  RETURN QUERY SELECT p_session_id, (v_user.totp_confirmed_at IS NOT NULL);
END
$$;

CREATE OR REPLACE FUNCTION portal.rpc_begin_totp_enrollment(p_ciphertext text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
BEGIN
  IF portal.current_user_id() IS NULL OR portal.current_session_id() IS NULL OR length(p_ciphertext) < 40 THEN
    RAISE EXCEPTION 'unauthorized';
  END IF;
  UPDATE portal.users
  SET totp_ciphertext = p_ciphertext, totp_confirmed_at = NULL, totp_last_counter = -1
  WHERE id = portal.current_user_id() AND revoked_at IS NULL;
  IF NOT FOUND THEN RAISE EXCEPTION 'unauthorized'; END IF;
  UPDATE portal.recovery_codes SET revoked_at = clock_timestamp()
  WHERE user_id = portal.current_user_id() AND consumed_at IS NULL AND revoked_at IS NULL;
END
$$;

CREATE OR REPLACE FUNCTION portal.get_totp_material_for_current_user()
RETURNS TABLE(totp_ciphertext text, totp_last_counter bigint, totp_confirmed boolean)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
  SELECT u.totp_ciphertext, u.totp_last_counter, u.totp_confirmed_at IS NOT NULL
  FROM portal.users u WHERE u.id = portal.current_user_id() AND u.revoked_at IS NULL
$$;

CREATE OR REPLACE FUNCTION portal.rpc_confirm_totp(p_counter bigint, p_step_up_until timestamptz, p_recovery_digests text[])
RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
DECLARE v_digest text;
BEGIN
  IF cardinality(p_recovery_digests) <> 10 OR p_step_up_until <= clock_timestamp() OR p_step_up_until > clock_timestamp() + interval '20 minutes' THEN
    RAISE EXCEPTION 'invalid TOTP confirmation';
  END IF;
  UPDATE portal.users
  SET totp_last_counter = p_counter, totp_confirmed_at = clock_timestamp()
  WHERE id = portal.current_user_id() AND totp_ciphertext IS NOT NULL AND p_counter > totp_last_counter;
  IF NOT FOUND THEN RAISE EXCEPTION 'invalid or replayed TOTP'; END IF;
  UPDATE portal.recovery_codes SET revoked_at = clock_timestamp()
  WHERE user_id = portal.current_user_id() AND consumed_at IS NULL AND revoked_at IS NULL;
  FOREACH v_digest IN ARRAY p_recovery_digests LOOP
    IF v_digest !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'invalid recovery digest'; END IF;
    INSERT INTO portal.recovery_codes(user_id,code_digest) VALUES (portal.current_user_id(),v_digest);
  END LOOP;
  UPDATE portal.sessions SET auth_level = 2, step_up_until = p_step_up_until
  WHERE id = portal.current_session_id() AND user_id = portal.current_user_id() AND revoked_at IS NULL;
  PERFORM portal.write_audit('portal.totp.confirmed','user',portal.current_user_id(),NULL,'{}'::jsonb);
END
$$;

CREATE OR REPLACE FUNCTION portal.rpc_step_up_totp(p_counter bigint, p_step_up_until timestamptz)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
BEGIN
  IF p_step_up_until <= clock_timestamp() OR p_step_up_until > clock_timestamp() + interval '20 minutes' THEN
    RAISE EXCEPTION 'invalid step-up expiry';
  END IF;
  UPDATE portal.users SET totp_last_counter = p_counter
  WHERE id = portal.current_user_id() AND totp_confirmed_at IS NOT NULL AND p_counter > totp_last_counter;
  IF NOT FOUND THEN RAISE EXCEPTION 'invalid or replayed TOTP'; END IF;
  UPDATE portal.sessions SET auth_level = 2, step_up_until = p_step_up_until
  WHERE id = portal.current_session_id() AND user_id = portal.current_user_id() AND revoked_at IS NULL;
  IF NOT FOUND THEN RAISE EXCEPTION 'invalid session'; END IF;
  PERFORM portal.write_audit('portal.session.step_up','session',portal.current_session_id(),NULL,jsonb_build_object('method','totp'));
END
$$;

CREATE OR REPLACE FUNCTION portal.rpc_use_recovery_code(p_digest text, p_step_up_until timestamptz)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
DECLARE v_id uuid;
BEGIN
  SELECT id INTO v_id FROM portal.recovery_codes
  WHERE user_id = portal.current_user_id() AND code_digest = p_digest
    AND consumed_at IS NULL AND revoked_at IS NULL
  FOR UPDATE;
  IF NOT FOUND THEN RETURN false; END IF;
  UPDATE portal.recovery_codes SET consumed_at = clock_timestamp() WHERE id = v_id;
  UPDATE portal.sessions SET auth_level = 2, step_up_until = LEAST(p_step_up_until, clock_timestamp() + interval '5 minutes')
  WHERE id = portal.current_session_id() AND user_id = portal.current_user_id() AND revoked_at IS NULL;
  PERFORM portal.write_audit('portal.session.recovered','session',portal.current_session_id(),NULL,jsonb_build_object('method','one_time_recovery_code'));
  RETURN true;
END
$$;

CREATE OR REPLACE FUNCTION portal.rpc_logout()
RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
BEGIN
  UPDATE portal.sessions SET revoked_at = clock_timestamp()
  WHERE id = portal.current_session_id() AND user_id = portal.current_user_id();
END
$$;

CREATE OR REPLACE FUNCTION portal.rpc_invite_user(
  p_invitation_id uuid,
  p_email citext,
  p_display_name text,
  p_household_id uuid,
  p_role portal.portal_role,
  p_entity_ids uuid[],
  p_token_digest text,
  p_token_ciphertext text,
  p_expires_at timestamptz
)
RETURNS TABLE(invitation_id uuid, user_id uuid, expires_at timestamptz)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
DECLARE v_user_id uuid; v_membership_id uuid; v_entity uuid;
BEGIN
  IF NOT portal.has_household_role(p_household_id, ARRAY['advisor']::portal.portal_role[]) OR NOT portal.has_current_step_up() THEN
    RAISE EXCEPTION 'forbidden';
  END IF;
  IF length(trim(p_display_name)) NOT BETWEEN 1 AND 120 OR p_expires_at <= clock_timestamp() OR p_expires_at > clock_timestamp() + interval '30 days' THEN
    RAISE EXCEPTION 'invalid invitation';
  END IF;
  INSERT INTO portal.users(email,display_name)
  VALUES (p_email,trim(p_display_name))
  ON CONFLICT (email) DO UPDATE SET display_name = EXCLUDED.display_name
    WHERE portal.users.revoked_at IS NULL
  RETURNING id INTO v_user_id;
  IF v_user_id IS NULL THEN RAISE EXCEPTION 'revoked user requires recovery review'; END IF;

  SELECT id INTO v_membership_id FROM portal.memberships
  WHERE user_id = v_user_id AND household_id = p_household_id AND revoked_at IS NULL
  FOR UPDATE;
  IF FOUND THEN
    UPDATE portal.memberships SET role = p_role WHERE id = v_membership_id;
    DELETE FROM portal.membership_entities WHERE membership_id = v_membership_id;
  ELSE
    INSERT INTO portal.memberships(user_id,household_id,role)
    VALUES (v_user_id,p_household_id,p_role) RETURNING id INTO v_membership_id;
  END IF;
  FOREACH v_entity IN ARRAY COALESCE(p_entity_ids,ARRAY[]::uuid[]) LOOP
    IF NOT EXISTS (SELECT 1 FROM portal.entities e WHERE e.id = v_entity AND e.household_id = p_household_id AND e.archived_at IS NULL) THEN
      RAISE EXCEPTION 'entity outside household';
    END IF;
    INSERT INTO portal.membership_entities(membership_id,entity_id) VALUES (v_membership_id,v_entity);
  END LOOP;
  UPDATE portal.invitations SET revoked_at = clock_timestamp()
  WHERE user_id = v_user_id AND consumed_at IS NULL AND revoked_at IS NULL;
  INSERT INTO portal.invitations(id,user_id,household_id,token_digest,created_by,expires_at)
  VALUES (p_invitation_id,v_user_id,p_household_id,p_token_digest,portal.current_user_id(),p_expires_at);
  INSERT INTO portal.outbox(channel,topic,aggregate_id,payload,secret_ciphertext)
  VALUES ('email','portal.invitation',p_invitation_id,
    jsonb_build_object('recipient',p_email::text,'template','portal_invitation','invitation_id',p_invitation_id),p_token_ciphertext);
  PERFORM portal.write_audit('portal.invitation.created','invitation',p_invitation_id,p_household_id,
    jsonb_build_object('user_id',v_user_id,'role',p_role));
  RETURN QUERY SELECT p_invitation_id,v_user_id,p_expires_at;
END
$$;

CREATE OR REPLACE FUNCTION portal.rpc_revoke_membership(p_user_id uuid, p_household_id uuid, p_reason text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
BEGIN
  IF NOT portal.has_household_role(p_household_id, ARRAY['advisor']::portal.portal_role[]) OR NOT portal.has_current_step_up() THEN
    RAISE EXCEPTION 'forbidden';
  END IF;
  UPDATE portal.memberships SET revoked_at = clock_timestamp()
  WHERE user_id = p_user_id AND household_id = p_household_id AND revoked_at IS NULL;
  IF NOT FOUND THEN RAISE EXCEPTION 'membership absent or already revoked'; END IF;
  UPDATE portal.users SET auth_epoch = auth_epoch + 1 WHERE id = p_user_id;
  UPDATE portal.sessions SET revoked_at = clock_timestamp() WHERE user_id = p_user_id AND revoked_at IS NULL;
  UPDATE portal.invitations SET revoked_at = clock_timestamp() WHERE user_id = p_user_id AND revoked_at IS NULL AND consumed_at IS NULL;
  UPDATE portal.magic_links SET revoked_at = clock_timestamp() WHERE user_id = p_user_id AND revoked_at IS NULL AND consumed_at IS NULL;
  PERFORM portal.write_audit('portal.membership.revoked','user',p_user_id,p_household_id,jsonb_build_object('reason',left(p_reason,240)));
END
$$;

REVOKE ALL ON FUNCTION portal.write_audit(text,text,uuid,uuid,jsonb,uuid,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.rpc_request_magic_link(uuid,citext,text,text,timestamptz) FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.rpc_consume_magic_link(text,uuid,text,timestamptz) FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.rpc_consume_invitation(text,uuid,text,timestamptz) FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.rpc_begin_totp_enrollment(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.get_totp_material_for_current_user() FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.rpc_confirm_totp(bigint,timestamptz,text[]) FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.rpc_step_up_totp(bigint,timestamptz) FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.rpc_use_recovery_code(text,timestamptz) FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.rpc_logout() FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.rpc_invite_user(uuid,citext,text,uuid,portal.portal_role,uuid[],text,text,timestamptz) FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.rpc_revoke_membership(uuid,uuid,text) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION portal.rpc_request_magic_link(uuid,citext,text,text,timestamptz) TO portal_api;
GRANT EXECUTE ON FUNCTION portal.rpc_consume_magic_link(text,uuid,text,timestamptz) TO portal_api;
GRANT EXECUTE ON FUNCTION portal.rpc_consume_invitation(text,uuid,text,timestamptz) TO portal_api;
GRANT EXECUTE ON FUNCTION portal.rpc_begin_totp_enrollment(text) TO portal_api;
GRANT EXECUTE ON FUNCTION portal.get_totp_material_for_current_user() TO portal_api;
GRANT EXECUTE ON FUNCTION portal.rpc_confirm_totp(bigint,timestamptz,text[]) TO portal_api;
GRANT EXECUTE ON FUNCTION portal.rpc_step_up_totp(bigint,timestamptz) TO portal_api;
GRANT EXECUTE ON FUNCTION portal.rpc_use_recovery_code(text,timestamptz) TO portal_api;
GRANT EXECUTE ON FUNCTION portal.rpc_logout() TO portal_api;
GRANT EXECUTE ON FUNCTION portal.rpc_invite_user(uuid,citext,text,uuid,portal.portal_role,uuid[],text,text,timestamptz) TO portal_api;
GRANT EXECUTE ON FUNCTION portal.rpc_revoke_membership(uuid,uuid,text) TO portal_api;

COMMIT;
