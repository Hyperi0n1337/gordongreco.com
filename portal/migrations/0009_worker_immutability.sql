BEGIN;

CREATE OR REPLACE FUNCTION portal.assert_worker()
RETURNS void LANGUAGE plpgsql STABLE SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
BEGIN
  IF current_setting('app.actor_role',true) IS DISTINCT FROM 'worker'
     OR nullif(current_setting('app.worker_id',true),'') IS NULL THEN RAISE EXCEPTION 'worker context required'; END IF;
END
$$;

CREATE OR REPLACE FUNCTION portal.worker_claim_scan_job()
RETURNS TABLE(
  document_id uuid,household_id uuid,original_filename text,quarantine_key text,
  authoritative_sha256 text,authoritative_size bigint
)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
DECLARE v_id uuid;
BEGIN
  PERFORM portal.assert_worker();
  SELECT s.document_id INTO v_id FROM portal.scan_jobs s
  JOIN portal.documents d ON d.id=s.document_id
  WHERE s.completed_at IS NULL AND s.available_at<=clock_timestamp()
    AND (s.claimed_at IS NULL OR s.claimed_at<clock_timestamp()-interval '10 minutes')
    AND d.state IN ('quarantined','scanning')
  ORDER BY s.available_at,s.document_id LIMIT 1 FOR UPDATE OF s SKIP LOCKED;
  IF NOT FOUND THEN RETURN; END IF;
  UPDATE portal.scan_jobs SET claimed_at=clock_timestamp(),claimed_by=current_setting('app.worker_id'),attempts=attempts+1 WHERE document_id=v_id;
  UPDATE portal.documents SET state='scanning',updated_at=clock_timestamp() WHERE id=v_id;
  RETURN QUERY SELECT d.id,d.household_id,d.original_filename,d.quarantine_key,d.authoritative_sha256::text,d.authoritative_size
  FROM portal.documents d WHERE d.id=v_id;
END
$$;

CREATE OR REPLACE FUNCTION portal.worker_reject_document(p_document_id uuid,p_mime text,p_reason text,p_findings jsonb)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
DECLARE v_doc portal.documents%ROWTYPE;
BEGIN
  PERFORM portal.assert_worker();
  SELECT * INTO v_doc FROM portal.documents WHERE id=p_document_id FOR UPDATE;
  IF NOT FOUND OR v_doc.state<>'scanning' THEN RAISE EXCEPTION 'document not scanning'; END IF;
  UPDATE portal.documents SET state='rejected',authoritative_content_type=p_mime,review_note=left(p_reason,1000),revision=revision+1,updated_at=clock_timestamp()
  WHERE id=p_document_id;
  UPDATE portal.scan_jobs SET completed_at=clock_timestamp(),claimed_at=NULL WHERE document_id=p_document_id;
  UPDATE portal.uploads SET state='complete',updated_at=clock_timestamp() WHERE document_id=p_document_id;
  UPDATE portal.document_requests SET status='missing',updated_at=clock_timestamp() WHERE id=v_doc.request_id;
  PERFORM portal.append_receipt(v_doc.household_id,v_doc.id,'document.scan_rejected',current_setting('app.worker_id'),jsonb_build_object(
    'sha256',v_doc.authoritative_sha256,'size',v_doc.authoritative_size,'mime',p_mime,'reason',left(p_reason,1000),'findings',p_findings
  ));
END
$$;

CREATE OR REPLACE FUNCTION portal.worker_accept_document(p_document_id uuid,p_mime text,p_clean_key text,p_findings jsonb)
RETURNS portal.document_state LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
DECLARE v_doc portal.documents%ROWTYPE; v_duplicate uuid; v_lock bigint;
BEGIN
  PERFORM portal.assert_worker();
  SELECT * INTO v_doc FROM portal.documents WHERE id=p_document_id FOR UPDATE;
  IF NOT FOUND OR v_doc.state<>'scanning' THEN RAISE EXCEPTION 'document not scanning'; END IF;
  IF p_clean_key !~ '^clean/[0-9a-f-]{36}/[0-9a-f-]{36}/[0-9a-f-]{36}$' THEN RAISE EXCEPTION 'invalid clean key'; END IF;
  v_lock:=hashtextextended(v_doc.household_id::text||':'||v_doc.authoritative_sha256,0);
  PERFORM pg_advisory_xact_lock(v_lock);
  SELECT id INTO v_duplicate FROM portal.documents
  WHERE id<>v_doc.id AND household_id=v_doc.household_id AND authoritative_sha256=v_doc.authoritative_sha256
    AND authoritative_size=v_doc.authoritative_size AND state IN ('ready_for_review','accepted') AND deleted_at IS NULL
  ORDER BY created_at LIMIT 1;
  IF v_duplicate IS NOT NULL THEN
    UPDATE portal.documents SET state='duplicate',duplicate_of=v_duplicate,clean_key=p_clean_key,authoritative_content_type=p_mime,
      revision=revision+1,updated_at=clock_timestamp() WHERE id=p_document_id;
    INSERT INTO portal.object_delete_jobs(document_id,final_state) VALUES (p_document_id,'duplicate')
    ON CONFLICT (document_id) DO UPDATE SET final_state='duplicate',available_at=clock_timestamp(),completed_at=NULL;
    PERFORM portal.append_receipt(v_doc.household_id,v_doc.id,'document.duplicate_detected',current_setting('app.worker_id'),jsonb_build_object(
      'duplicate_of',v_duplicate,'sha256',v_doc.authoritative_sha256,'size',v_doc.authoritative_size
    ));
  ELSE
    UPDATE portal.documents SET state='ready_for_review',clean_key=p_clean_key,authoritative_content_type=p_mime,
      revision=revision+1,updated_at=clock_timestamp() WHERE id=p_document_id;
    UPDATE portal.document_requests SET status='review',updated_at=clock_timestamp() WHERE id=v_doc.request_id;
    PERFORM portal.append_receipt(v_doc.household_id,v_doc.id,'document.clean_stored',current_setting('app.worker_id'),jsonb_build_object(
      'sha256',v_doc.authoritative_sha256,'size',v_doc.authoritative_size,'mime',p_mime,'clean_key',p_clean_key,'findings',p_findings
    ));
  END IF;
  UPDATE portal.scan_jobs SET completed_at=clock_timestamp(),claimed_at=NULL WHERE document_id=p_document_id;
  UPDATE portal.uploads SET state='complete',updated_at=clock_timestamp() WHERE document_id=p_document_id;
  RETURN CASE WHEN v_duplicate IS NULL THEN 'ready_for_review'::portal.document_state ELSE 'duplicate'::portal.document_state END;
END
$$;

CREATE OR REPLACE FUNCTION portal.worker_retry_scan(p_document_id uuid,p_error text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
DECLARE v_attempts integer;
BEGIN
  PERFORM portal.assert_worker();
  SELECT attempts INTO v_attempts FROM portal.scan_jobs WHERE document_id=p_document_id FOR UPDATE;
  UPDATE portal.scan_jobs SET claimed_at=NULL,claimed_by=NULL,last_error=left(p_error,1000),
    available_at=clock_timestamp()+make_interval(secs=>LEAST(3600,(2^LEAST(v_attempts,10))::integer))
  WHERE document_id=p_document_id AND completed_at IS NULL;
  UPDATE portal.documents SET state='quarantined',review_note='security scan pending; fail-closed retry',updated_at=clock_timestamp()
  WHERE id=p_document_id AND state='scanning';
END
$$;

CREATE OR REPLACE FUNCTION portal.worker_claim_delete_job()
RETURNS TABLE(document_id uuid,clean_key text,quarantine_key text,final_state portal.document_state)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
DECLARE v_id uuid;
BEGIN
  PERFORM portal.assert_worker();
  SELECT j.document_id INTO v_id FROM portal.object_delete_jobs j
  WHERE j.completed_at IS NULL AND j.available_at<=clock_timestamp()
    AND (j.claimed_at IS NULL OR j.claimed_at<clock_timestamp()-interval '10 minutes')
  ORDER BY j.available_at LIMIT 1 FOR UPDATE SKIP LOCKED;
  IF NOT FOUND THEN RETURN; END IF;
  UPDATE portal.object_delete_jobs SET claimed_at=clock_timestamp(),claimed_by=current_setting('app.worker_id'),attempts=attempts+1 WHERE document_id=v_id;
  RETURN QUERY
  SELECT d.id,d.clean_key,d.quarantine_key,j.final_state
  FROM portal.documents d JOIN portal.object_delete_jobs j ON j.document_id=d.id
  WHERE d.id=v_id;
END
$$;

CREATE OR REPLACE FUNCTION portal.worker_complete_delete(p_document_id uuid)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
DECLARE v_doc portal.documents%ROWTYPE; v_final_state portal.document_state; v_event text;
BEGIN
  PERFORM portal.assert_worker();
  SELECT * INTO v_doc FROM portal.documents WHERE id=p_document_id FOR UPDATE;
  SELECT final_state INTO v_final_state FROM portal.object_delete_jobs WHERE document_id=p_document_id FOR UPDATE;
  IF NOT FOUND OR v_final_state NOT IN ('duplicate','deleted') THEN RAISE EXCEPTION 'invalid delete job'; END IF;
  UPDATE portal.documents
  SET state=v_final_state,clean_key=NULL,
      deleted_at=CASE WHEN v_final_state='deleted' THEN clock_timestamp() ELSE NULL END,
      revision=revision+1,updated_at=clock_timestamp()
  WHERE id=p_document_id;
  UPDATE portal.object_delete_jobs SET completed_at=clock_timestamp(),claimed_at=NULL WHERE document_id=p_document_id;
  v_event:=CASE WHEN v_final_state='deleted' THEN 'document.deleted' ELSE 'document.duplicate_object_deleted' END;
  PERFORM portal.append_receipt(v_doc.household_id,v_doc.id,v_event,current_setting('app.worker_id'),jsonb_build_object(
    'authoritative_sha256',v_doc.authoritative_sha256,'authoritative_size',v_doc.authoritative_size,
    'object_bytes_deleted',true,'final_state',v_final_state
  ));
END
$$;

CREATE OR REPLACE FUNCTION portal.worker_retry_delete(p_document_id uuid,p_error text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
DECLARE v_attempts integer;
BEGIN
  PERFORM portal.assert_worker();
  SELECT attempts INTO v_attempts FROM portal.object_delete_jobs WHERE document_id=p_document_id FOR UPDATE;
  UPDATE portal.object_delete_jobs SET claimed_at=NULL,claimed_by=NULL,last_error=left(p_error,1000),
    available_at=clock_timestamp()+make_interval(secs=>LEAST(3600,(2^LEAST(v_attempts,10))::integer)) WHERE document_id=p_document_id;
END
$$;

CREATE OR REPLACE FUNCTION portal.worker_claim_outbox()
RETURNS SETOF portal.outbox LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
DECLARE v_id uuid;
BEGIN
  PERFORM portal.assert_worker();
  SELECT id INTO v_id FROM portal.outbox
  WHERE delivered_at IS NULL AND channel<>'worker' AND available_at<=clock_timestamp()
    AND (claimed_at IS NULL OR claimed_at<clock_timestamp()-interval '10 minutes')
  ORDER BY available_at,created_at LIMIT 1 FOR UPDATE SKIP LOCKED;
  IF NOT FOUND THEN RETURN; END IF;
  UPDATE portal.outbox SET claimed_at=clock_timestamp(),attempts=attempts+1 WHERE id=v_id;
  RETURN QUERY SELECT * FROM portal.outbox WHERE id=v_id;
END
$$;

CREATE OR REPLACE FUNCTION portal.worker_complete_outbox(p_id uuid)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$ BEGIN PERFORM portal.assert_worker(); UPDATE portal.outbox SET delivered_at=clock_timestamp(),claimed_at=NULL,last_error=NULL WHERE id=p_id; END $$;
CREATE OR REPLACE FUNCTION portal.worker_release_outbox(p_id uuid)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$ BEGIN PERFORM portal.assert_worker(); UPDATE portal.outbox SET claimed_at=NULL WHERE id=p_id; END $$;
CREATE OR REPLACE FUNCTION portal.worker_retry_outbox(p_id uuid,p_error text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
DECLARE v_attempts integer;
BEGIN
  PERFORM portal.assert_worker(); SELECT attempts INTO v_attempts FROM portal.outbox WHERE id=p_id FOR UPDATE;
  UPDATE portal.outbox SET claimed_at=NULL,last_error=left(p_error,1000),available_at=clock_timestamp()+make_interval(secs=>LEAST(3600,(2^LEAST(v_attempts,10))::integer)) WHERE id=p_id;
END
$$;

CREATE OR REPLACE FUNCTION portal.worker_claim_recalculation()
RETURNS SETOF portal.recalculation_jobs LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
DECLARE v_id uuid;
BEGIN
  PERFORM portal.assert_worker();
  SELECT id INTO v_id FROM portal.recalculation_jobs WHERE completed_at IS NULL AND available_at<=clock_timestamp()
    AND (claimed_at IS NULL OR claimed_at<clock_timestamp()-interval '10 minutes')
  ORDER BY available_at,requested_at LIMIT 1 FOR UPDATE SKIP LOCKED;
  IF NOT FOUND THEN RETURN; END IF;
  UPDATE portal.recalculation_jobs SET claimed_at=clock_timestamp(),attempts=attempts+1 WHERE id=v_id;
  RETURN QUERY SELECT * FROM portal.recalculation_jobs WHERE id=v_id;
END
$$;
CREATE OR REPLACE FUNCTION portal.worker_complete_recalculation(p_id uuid)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$ BEGIN PERFORM portal.assert_worker(); UPDATE portal.recalculation_jobs SET completed_at=clock_timestamp(),claimed_at=NULL,last_error=NULL WHERE id=p_id; END $$;
CREATE OR REPLACE FUNCTION portal.worker_retry_recalculation(p_id uuid,p_error text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
DECLARE v_attempts integer;
BEGIN
  PERFORM portal.assert_worker(); SELECT attempts INTO v_attempts FROM portal.recalculation_jobs WHERE id=p_id FOR UPDATE;
  UPDATE portal.recalculation_jobs SET claimed_at=NULL,last_error=left(p_error,1000),available_at=clock_timestamp()+make_interval(secs=>LEAST(3600,(2^LEAST(v_attempts,10))::integer)) WHERE id=p_id;
END
$$;

CREATE OR REPLACE FUNCTION portal.worker_activate_due_policies()
RETURNS integer LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
DECLARE v_count integer;
BEGIN
  PERFORM portal.assert_worker();
  WITH ranked AS (
    SELECT id,row_number() OVER(PARTITION BY household_id ORDER BY effective_at DESC,version DESC) AS rn
    FROM portal.treasury_policy_versions WHERE state IN ('approved','superseded') AND effective_at<=clock_timestamp()
  ), changed AS (
    UPDATE portal.treasury_policy_versions p SET state=CASE WHEN r.rn=1 THEN 'approved'::portal.policy_state ELSE 'superseded'::portal.policy_state END
    FROM ranked r WHERE p.id=r.id AND p.state IS DISTINCT FROM CASE WHEN r.rn=1 THEN 'approved'::portal.policy_state ELSE 'superseded'::portal.policy_state END
    RETURNING p.id
  ) SELECT count(*) INTO v_count FROM changed;
  RETURN v_count;
END
$$;

CREATE OR REPLACE FUNCTION portal.deny_update_delete()
RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, portal
AS $$ BEGIN RAISE EXCEPTION '% is append-only',TG_TABLE_NAME; END $$;
CREATE TRIGGER immutable_receipts_no_mutation BEFORE UPDATE OR DELETE ON portal.immutable_receipts FOR EACH ROW EXECUTE FUNCTION portal.deny_update_delete();
CREATE TRIGGER audit_events_no_mutation BEFORE UPDATE OR DELETE ON portal.audit_events FOR EACH ROW EXECUTE FUNCTION portal.deny_update_delete();
CREATE TRIGGER workflow_approvals_no_mutation BEFORE UPDATE OR DELETE ON portal.workflow_approvals FOR EACH ROW EXECUTE FUNCTION portal.deny_update_delete();

CREATE OR REPLACE FUNCTION portal.guard_policy_immutability()
RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, portal
AS $$
BEGIN
  IF OLD.state IN ('approved','superseded') AND (
    NEW.household_id<>OLD.household_id OR NEW.version<>OLD.version OR NEW.base_version_id IS DISTINCT FROM OLD.base_version_id
    OR NEW.effective_at<>OLD.effective_at OR NEW.terms<>OLD.terms OR NEW.signer_user_ids<>OLD.signer_user_ids
    OR NEW.approval_threshold<>OLD.approval_threshold OR NEW.created_by<>OLD.created_by OR NEW.idempotency_key<>OLD.idempotency_key
  ) THEN RAISE EXCEPTION 'approved treasury policy content is immutable'; END IF;
  RETURN NEW;
END
$$;
CREATE TRIGGER policy_immutability BEFORE UPDATE ON portal.treasury_policy_versions FOR EACH ROW EXECUTE FUNCTION portal.guard_policy_immutability();

CREATE OR REPLACE FUNCTION portal.guard_cash_immutability()
RETURNS trigger LANGUAGE plpgsql
SET search_path = pg_catalog, portal
AS $$
BEGIN
  IF NEW.household_id<>OLD.household_id OR NEW.entity_id IS DISTINCT FROM OLD.entity_id OR NEW.policy_version_id<>OLD.policy_version_id
     OR NEW.operation_type<>OLD.operation_type OR NEW.amount_minor<>OLD.amount_minor OR NEW.currency<>OLD.currency
     OR NEW.requested_effective_at<>OLD.requested_effective_at OR NEW.rationale<>OLD.rationale OR NEW.conflict_key<>OLD.conflict_key
     OR NEW.signer_user_ids<>OLD.signer_user_ids OR NEW.approval_threshold<>OLD.approval_threshold OR NEW.created_by<>OLD.created_by
     OR NEW.idempotency_key<>OLD.idempotency_key OR NEW.execution_state<>'not_executable' THEN
    RAISE EXCEPTION 'cash operation instruction fields are immutable';
  END IF;
  RETURN NEW;
END
$$;
CREATE TRIGGER cash_immutability BEFORE UPDATE ON portal.cash_operations FOR EACH ROW EXECUTE FUNCTION portal.guard_cash_immutability();

REVOKE ALL ON ALL FUNCTIONS IN SCHEMA portal FROM PUBLIC;

REVOKE ALL ON FUNCTION portal.assert_worker() FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.worker_claim_scan_job() FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.worker_reject_document(uuid,text,text,jsonb) FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.worker_accept_document(uuid,text,text,jsonb) FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.worker_retry_scan(uuid,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.worker_claim_delete_job() FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.worker_complete_delete(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.worker_retry_delete(uuid,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.worker_claim_outbox() FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.worker_complete_outbox(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.worker_release_outbox(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.worker_retry_outbox(uuid,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.worker_claim_recalculation() FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.worker_complete_recalculation(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.worker_retry_recalculation(uuid,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.worker_activate_due_policies() FROM PUBLIC;

GRANT EXECUTE ON FUNCTION portal.worker_claim_scan_job() TO portal_worker;
GRANT EXECUTE ON FUNCTION portal.worker_reject_document(uuid,text,text,jsonb) TO portal_worker;
GRANT EXECUTE ON FUNCTION portal.worker_accept_document(uuid,text,text,jsonb) TO portal_worker;
GRANT EXECUTE ON FUNCTION portal.worker_retry_scan(uuid,text) TO portal_worker;
GRANT EXECUTE ON FUNCTION portal.worker_claim_delete_job() TO portal_worker;
GRANT EXECUTE ON FUNCTION portal.worker_complete_delete(uuid) TO portal_worker;
GRANT EXECUTE ON FUNCTION portal.worker_retry_delete(uuid,text) TO portal_worker;
GRANT EXECUTE ON FUNCTION portal.worker_claim_outbox() TO portal_worker;
GRANT EXECUTE ON FUNCTION portal.worker_complete_outbox(uuid) TO portal_worker;
GRANT EXECUTE ON FUNCTION portal.worker_release_outbox(uuid) TO portal_worker;
GRANT EXECUTE ON FUNCTION portal.worker_retry_outbox(uuid,text) TO portal_worker;
GRANT EXECUTE ON FUNCTION portal.worker_claim_recalculation() TO portal_worker;
GRANT EXECUTE ON FUNCTION portal.worker_complete_recalculation(uuid) TO portal_worker;
GRANT EXECUTE ON FUNCTION portal.worker_retry_recalculation(uuid,text) TO portal_worker;
GRANT EXECUTE ON FUNCTION portal.worker_activate_due_policies() TO portal_worker;

COMMIT;
