BEGIN;

CREATE OR REPLACE FUNCTION portal.validate_treasury_terms(p_terms jsonb)
RETURNS jsonb LANGUAGE plpgsql IMMUTABLE
SET search_path = pg_catalog, portal
AS $$
DECLARE v_currency text; v_reserve bigint; v_limit bigint; v_item text;
BEGIN
  IF jsonb_typeof(p_terms)<>'object' OR NOT (p_terms ?& ARRAY['currency','minimum_operating_reserve_minor','cash_operation_limit_minor','permitted_operation_types']) THEN
    RAISE EXCEPTION 'missing treasury terms';
  END IF;
  v_currency:=upper(p_terms->>'currency'); v_reserve:=(p_terms->>'minimum_operating_reserve_minor')::bigint; v_limit:=(p_terms->>'cash_operation_limit_minor')::bigint;
  IF v_currency !~ '^[A-Z]{3}$' OR v_reserve<0 OR v_limit<=0 OR jsonb_typeof(p_terms->'permitted_operation_types')<>'array' THEN
    RAISE EXCEPTION 'invalid treasury terms';
  END IF;
  FOR v_item IN SELECT jsonb_array_elements_text(p_terms->'permitted_operation_types') LOOP
    IF v_item NOT IN ('operating_reserve_adjustment','planned_tax_payment_reserve','same_entity_liquidity_allocation','external_cash_need_notice') THEN
      RAISE EXCEPTION 'unsupported treasury operation type';
    END IF;
  END LOOP;
  IF jsonb_array_length(p_terms->'permitted_operation_types')=0 THEN RAISE EXCEPTION 'permitted operations required'; END IF;
  RETURN jsonb_build_object(
    'currency',v_currency,
    'minimum_operating_reserve_minor',v_reserve,
    'cash_operation_limit_minor',v_limit,
    'permitted_operation_types',p_terms->'permitted_operation_types',
    'notes',left(COALESCE(p_terms->>'notes',''),2000)
  );
END
$$;

CREATE OR REPLACE FUNCTION portal.rpc_propose_treasury_policy(
  p_household_id uuid,
  p_base_version_id uuid,
  p_effective_at timestamptz,
  p_terms jsonb,
  p_signer_user_ids uuid[],
  p_approval_threshold integer,
  p_idempotency_key text
)
RETURNS SETOF portal.treasury_policy_versions
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
DECLARE v_existing uuid; v_id uuid; v_version integer; v_base portal.treasury_policy_versions%ROWTYPE; v_signer uuid; v_terms jsonb;
BEGIN
  IF NOT portal.has_household_role(p_household_id,ARRAY['advisor']::portal.portal_role[]) OR NOT portal.has_current_step_up() THEN RAISE EXCEPTION 'forbidden'; END IF;
  SELECT id INTO v_existing FROM portal.treasury_policy_versions WHERE household_id=p_household_id AND idempotency_key=p_idempotency_key;
  IF FOUND THEN RETURN QUERY SELECT * FROM portal.treasury_policy_versions WHERE id=v_existing; RETURN; END IF;
  IF p_effective_at<=clock_timestamp()+interval '5 minutes' OR p_idempotency_key !~ '^[A-Za-z0-9._:-]{8,128}$' THEN RAISE EXCEPTION 'invalid future effective policy'; END IF;
  IF cardinality(p_signer_user_ids) NOT BETWEEN 1 AND 20 OR p_approval_threshold NOT BETWEEN 1 AND cardinality(p_signer_user_ids)
     OR cardinality(ARRAY(SELECT DISTINCT unnest(p_signer_user_ids)))<>cardinality(p_signer_user_ids) THEN RAISE EXCEPTION 'invalid signer set'; END IF;
  FOREACH v_signer IN ARRAY p_signer_user_ids LOOP
    IF NOT EXISTS (SELECT 1 FROM portal.memberships m WHERE m.user_id=v_signer AND m.household_id=p_household_id AND m.revoked_at IS NULL) THEN
      RAISE EXCEPTION 'signer outside household';
    END IF;
  END LOOP;
  IF NOT EXISTS (SELECT 1 FROM portal.memberships m WHERE m.user_id=ANY(p_signer_user_ids) AND m.household_id=p_household_id AND m.role='advisor' AND m.revoked_at IS NULL) THEN
    RAISE EXCEPTION 'advisor signer required';
  END IF;
  v_terms:=portal.validate_treasury_terms(p_terms);
  IF p_base_version_id IS NULL THEN
    IF EXISTS (SELECT 1 FROM portal.treasury_policy_versions WHERE household_id=p_household_id) THEN RAISE EXCEPTION 'initial policy already exists'; END IF;
    v_version:=1;
  ELSE
    SELECT * INTO v_base FROM portal.treasury_policy_versions WHERE id=p_base_version_id AND household_id=p_household_id AND state='approved' FOR SHARE;
    IF NOT FOUND THEN RAISE EXCEPTION 'approved base policy required'; END IF;
    IF v_base.id<>(SELECT id FROM portal.treasury_policy_versions WHERE household_id=p_household_id ORDER BY version DESC LIMIT 1) THEN RAISE EXCEPTION 'stale base policy'; END IF;
    IF p_effective_at<=v_base.effective_at THEN RAISE EXCEPTION 'effective time must follow base'; END IF;
    v_version:=v_base.version+1;
  END IF;
  v_id:=gen_random_uuid();
  INSERT INTO portal.treasury_policy_versions(
    id,household_id,version,base_version_id,effective_at,terms,signer_user_ids,approval_threshold,state,created_by,idempotency_key
  ) VALUES (
    v_id,p_household_id,v_version,p_base_version_id,p_effective_at,v_terms,p_signer_user_ids,p_approval_threshold,'pending_approval',portal.current_user_id(),p_idempotency_key
  );
  PERFORM portal.write_audit('treasury.policy.proposed','treasury_policy',v_id,p_household_id,jsonb_build_object('version',v_version,'base_version_id',p_base_version_id));
  RETURN QUERY SELECT * FROM portal.treasury_policy_versions WHERE id=v_id;
END
$$;

CREATE OR REPLACE FUNCTION portal.rpc_approve_treasury_policy(p_policy_id uuid,p_expected_revision integer)
RETURNS SETOF portal.treasury_policy_versions
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
DECLARE v_policy portal.treasury_policy_versions%ROWTYPE; v_count integer; v_advisor boolean; v_latest uuid;
BEGIN
  SELECT * INTO v_policy FROM portal.treasury_policy_versions WHERE id=p_policy_id FOR UPDATE;
  IF NOT FOUND OR NOT portal.can_household(v_policy.household_id) OR NOT portal.has_current_step_up() THEN RAISE EXCEPTION 'forbidden'; END IF;
  IF v_policy.state='approved' THEN RETURN QUERY SELECT * FROM portal.treasury_policy_versions WHERE id=p_policy_id; RETURN; END IF;
  IF v_policy.state<>'pending_approval' OR v_policy.revision<>p_expected_revision THEN RAISE EXCEPTION 'revision conflict'; END IF;
  IF NOT portal.current_user_id()=ANY(v_policy.signer_user_ids) THEN RAISE EXCEPTION 'not a designated signer'; END IF;
  INSERT INTO portal.workflow_approvals(workflow_type,workflow_id,signer_user_id,workflow_revision)
  VALUES ('treasury_policy',v_policy.id,portal.current_user_id(),v_policy.revision)
  ON CONFLICT (workflow_type,workflow_id,signer_user_id) DO NOTHING;
  SELECT count(DISTINCT a.signer_user_id),bool_or(m.role='advisor') INTO v_count,v_advisor
  FROM portal.workflow_approvals a
  JOIN portal.memberships m ON m.user_id=a.signer_user_id AND m.household_id=v_policy.household_id AND m.revoked_at IS NULL
  WHERE a.workflow_type='treasury_policy' AND a.workflow_id=v_policy.id;
  IF v_count>=v_policy.approval_threshold AND COALESCE(v_advisor,false) THEN
    IF v_policy.base_version_id IS NOT NULL THEN
      SELECT id INTO v_latest FROM portal.treasury_policy_versions
      WHERE household_id=v_policy.household_id AND state='approved' ORDER BY version DESC LIMIT 1;
      IF v_latest IS DISTINCT FROM v_policy.base_version_id THEN RAISE EXCEPTION 'base changed before final approval'; END IF;
    END IF;
    UPDATE portal.treasury_policy_versions SET state='approved',approved_at=clock_timestamp(),revision=revision+1 WHERE id=v_policy.id;
    INSERT INTO portal.outbox(channel,topic,aggregate_id,payload) VALUES
      ('mas_intake','mas.treasury_policy.approved',v_policy.id,jsonb_build_object(
        'direction','outbound_only','workflow_kind','treasury_policy_amendment','policy_version_id',v_policy.id,
        'household_id',v_policy.household_id,'effective_at',v_policy.effective_at,'execution','none'
      )),
      ('telegram','treasury.policy.approved',v_policy.id,jsonb_build_object(
        'template','treasury_policy_approved','policy_version_id',v_policy.id,'household_id',v_policy.household_id,'contains_client_documents',false
      ));
    INSERT INTO portal.recalculation_jobs(household_id,reason,source_id)
    VALUES (v_policy.household_id,'treasury_policy_version_approved',v_policy.id);
    PERFORM portal.write_audit('treasury.policy.approved','treasury_policy',v_policy.id,v_policy.household_id,jsonb_build_object('version',v_policy.version));
  END IF;
  RETURN QUERY SELECT * FROM portal.treasury_policy_versions WHERE id=p_policy_id;
END
$$;

CREATE OR REPLACE FUNCTION portal.rpc_request_cash_operation(
  p_household_id uuid,
  p_entity_id uuid,
  p_policy_version_id uuid,
  p_operation_type text,
  p_amount_minor bigint,
  p_currency text,
  p_requested_effective_at timestamptz,
  p_rationale text,
  p_conflict_key text,
  p_idempotency_key text
)
RETURNS SETOF portal.cash_operations
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
DECLARE v_policy portal.treasury_policy_versions%ROWTYPE; v_existing uuid; v_id uuid;
BEGIN
  IF NOT portal.can_entity(p_household_id,p_entity_id) THEN RAISE EXCEPTION 'forbidden'; END IF;
  SELECT id INTO v_existing FROM portal.cash_operations WHERE household_id=p_household_id AND idempotency_key=p_idempotency_key;
  IF FOUND THEN RETURN QUERY SELECT * FROM portal.cash_operations WHERE id=v_existing; RETURN; END IF;
  SELECT * INTO v_policy FROM portal.treasury_policy_versions
  WHERE id=p_policy_version_id AND household_id=p_household_id AND state='approved' FOR SHARE;
  IF NOT FOUND THEN RAISE EXCEPTION 'approved policy required'; END IF;
  IF p_requested_effective_at<GREATEST(clock_timestamp(),v_policy.effective_at) THEN RAISE EXCEPTION 'effective time conflicts with policy'; END IF;
  IF p_operation_type NOT IN (SELECT jsonb_array_elements_text(v_policy.terms->'permitted_operation_types')) THEN RAISE EXCEPTION 'operation not permitted'; END IF;
  IF p_amount_minor<=0 OR p_amount_minor>(v_policy.terms->>'cash_operation_limit_minor')::bigint THEN RAISE EXCEPTION 'amount outside policy'; END IF;
  IF upper(p_currency)<>v_policy.terms->>'currency' THEN RAISE EXCEPTION 'currency conflict'; END IF;
  IF length(trim(p_rationale)) NOT BETWEEN 1 AND 2000 OR length(trim(p_conflict_key)) NOT BETWEEN 1 AND 160
     OR p_idempotency_key !~ '^[A-Za-z0-9._:-]{8,128}$' THEN RAISE EXCEPTION 'invalid cash operation'; END IF;
  v_id:=gen_random_uuid();
  INSERT INTO portal.cash_operations(
    id,household_id,entity_id,policy_version_id,operation_type,amount_minor,currency,requested_effective_at,rationale,
    conflict_key,signer_user_ids,approval_threshold,state,created_by,idempotency_key
  ) VALUES (
    v_id,p_household_id,p_entity_id,v_policy.id,p_operation_type,p_amount_minor,upper(p_currency),p_requested_effective_at,trim(p_rationale),
    trim(p_conflict_key),v_policy.signer_user_ids,v_policy.approval_threshold,'pending_approval',portal.current_user_id(),p_idempotency_key
  );
  PERFORM portal.write_audit('treasury.cash_operation.requested','cash_operation',v_id,p_household_id,
    jsonb_build_object('entity_id',p_entity_id,'execution_state','not_executable'));
  RETURN QUERY SELECT * FROM portal.cash_operations WHERE id=v_id;
END
$$;

CREATE OR REPLACE FUNCTION portal.rpc_approve_cash_operation(p_operation_id uuid,p_expected_revision integer)
RETURNS SETOF portal.cash_operations
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
DECLARE v_operation portal.cash_operations%ROWTYPE; v_count integer; v_advisor boolean;
BEGIN
  SELECT * INTO v_operation FROM portal.cash_operations WHERE id=p_operation_id FOR UPDATE;
  IF NOT FOUND OR NOT portal.can_entity(v_operation.household_id,v_operation.entity_id) OR NOT portal.has_current_step_up() THEN RAISE EXCEPTION 'forbidden'; END IF;
  IF v_operation.state='approved_for_intake' THEN RETURN QUERY SELECT * FROM portal.cash_operations WHERE id=p_operation_id; RETURN; END IF;
  IF v_operation.state<>'pending_approval' OR v_operation.revision<>p_expected_revision THEN RAISE EXCEPTION 'revision conflict'; END IF;
  IF NOT portal.current_user_id()=ANY(v_operation.signer_user_ids) THEN RAISE EXCEPTION 'not a designated signer'; END IF;
  IF NOT EXISTS (SELECT 1 FROM portal.treasury_policy_versions p WHERE p.id=v_operation.policy_version_id AND p.state IN ('approved','superseded')) THEN
    RAISE EXCEPTION 'governing policy invalid';
  END IF;
  INSERT INTO portal.workflow_approvals(workflow_type,workflow_id,signer_user_id,workflow_revision)
  VALUES ('cash_operation',v_operation.id,portal.current_user_id(),v_operation.revision)
  ON CONFLICT (workflow_type,workflow_id,signer_user_id) DO NOTHING;
  SELECT count(DISTINCT a.signer_user_id),bool_or(m.role='advisor') INTO v_count,v_advisor
  FROM portal.workflow_approvals a
  JOIN portal.memberships m ON m.user_id=a.signer_user_id AND m.household_id=v_operation.household_id AND m.revoked_at IS NULL
  WHERE a.workflow_type='cash_operation' AND a.workflow_id=v_operation.id;
  IF v_count>=v_operation.approval_threshold AND COALESCE(v_advisor,false) THEN
    UPDATE portal.cash_operations SET state='approved_for_intake',approved_at=clock_timestamp(),revision=revision+1 WHERE id=v_operation.id;
    INSERT INTO portal.outbox(channel,topic,aggregate_id,payload) VALUES
      ('mas_intake','mas.cash_operation.approved_for_intake',v_operation.id,jsonb_build_object(
        'direction','outbound_only','workflow_kind','cash_operation','cash_operation_id',v_operation.id,
        'household_id',v_operation.household_id,'entity_id',v_operation.entity_id,'execution','none','trade','none','money_movement','none'
      )),
      ('telegram','treasury.cash_operation.approved',v_operation.id,jsonb_build_object(
        'template','cash_operation_approved_for_intake','cash_operation_id',v_operation.id,'household_id',v_operation.household_id,'contains_bank_coordinates',false
      ));
    INSERT INTO portal.recalculation_jobs(household_id,reason,source_id)
    VALUES (v_operation.household_id,'cash_operation_approved_for_intake',v_operation.id);
    PERFORM portal.write_audit('treasury.cash_operation.approved_for_intake','cash_operation',v_operation.id,v_operation.household_id,
      jsonb_build_object('execution','none','trade','none','money_movement','none'));
  END IF;
  RETURN QUERY SELECT * FROM portal.cash_operations WHERE id=p_operation_id;
END
$$;

CREATE OR REPLACE FUNCTION portal.rpc_cancel_cash_operation(p_operation_id uuid,p_expected_revision integer)
RETURNS SETOF portal.cash_operations
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
DECLARE v_operation portal.cash_operations%ROWTYPE;
BEGIN
  SELECT * INTO v_operation FROM portal.cash_operations WHERE id=p_operation_id FOR UPDATE;
  IF NOT FOUND OR NOT portal.can_entity(v_operation.household_id,v_operation.entity_id) THEN RAISE EXCEPTION 'forbidden'; END IF;
  IF portal.current_user_id()<>v_operation.created_by AND NOT portal.has_household_role(v_operation.household_id,ARRAY['advisor']::portal.portal_role[]) THEN RAISE EXCEPTION 'forbidden'; END IF;
  IF v_operation.state<>'pending_approval' OR v_operation.revision<>p_expected_revision THEN RAISE EXCEPTION 'revision conflict'; END IF;
  UPDATE portal.cash_operations SET state='cancelled',revision=revision+1 WHERE id=v_operation.id;
  PERFORM portal.write_audit('treasury.cash_operation.cancelled','cash_operation',v_operation.id,v_operation.household_id,'{}'::jsonb);
  RETURN QUERY SELECT * FROM portal.cash_operations WHERE id=p_operation_id;
END
$$;

REVOKE ALL ON FUNCTION portal.validate_treasury_terms(jsonb) FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.rpc_propose_treasury_policy(uuid,uuid,timestamptz,jsonb,uuid[],integer,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.rpc_approve_treasury_policy(uuid,integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.rpc_request_cash_operation(uuid,uuid,uuid,text,bigint,text,timestamptz,text,text,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.rpc_approve_cash_operation(uuid,integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.rpc_cancel_cash_operation(uuid,integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION portal.rpc_propose_treasury_policy(uuid,uuid,timestamptz,jsonb,uuid[],integer,text) TO portal_api;
GRANT EXECUTE ON FUNCTION portal.rpc_approve_treasury_policy(uuid,integer) TO portal_api;
GRANT EXECUTE ON FUNCTION portal.rpc_request_cash_operation(uuid,uuid,uuid,text,bigint,text,timestamptz,text,text,text) TO portal_api;
GRANT EXECUTE ON FUNCTION portal.rpc_approve_cash_operation(uuid,integer) TO portal_api;
GRANT EXECUTE ON FUNCTION portal.rpc_cancel_cash_operation(uuid,integer) TO portal_api;

COMMIT;
