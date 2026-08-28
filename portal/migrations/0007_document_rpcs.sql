BEGIN;

CREATE OR REPLACE FUNCTION portal.append_receipt(
  p_household_id uuid,
  p_document_id uuid,
  p_event_type text,
  p_actor_id text,
  p_payload jsonb
)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
DECLARE v_id uuid := gen_random_uuid(); v_at timestamptz := clock_timestamp(); v_hash text;
BEGIN
  v_hash := encode(digest(convert_to(jsonb_build_object(
    'id',v_id,'household_id',p_household_id,'document_id',p_document_id,
    'event_type',p_event_type,'event_at',v_at,'actor_id',p_actor_id,'payload',p_payload
  )::text,'UTF8'),'sha256'),'hex');
  INSERT INTO portal.immutable_receipts(id,household_id,document_id,event_type,event_at,actor_id,payload,receipt_sha256)
  VALUES (v_id,p_household_id,p_document_id,p_event_type,v_at,p_actor_id,p_payload,v_hash);
  RETURN v_id;
END
$$;

CREATE OR REPLACE FUNCTION portal.rpc_create_document_request(
  p_household_id uuid,
  p_entity_id uuid,
  p_title text,
  p_description text,
  p_due_at timestamptz
)
RETURNS SETOF portal.document_requests
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
DECLARE v_id uuid;
BEGIN
  IF NOT portal.can_entity(p_household_id,p_entity_id)
     OR NOT portal.has_household_role(p_household_id,ARRAY['advisor','operations']::portal.portal_role[]) THEN
    RAISE EXCEPTION 'forbidden';
  END IF;
  IF length(trim(p_title)) NOT BETWEEN 1 AND 160 OR length(COALESCE(p_description,'')) > 2000 THEN
    RAISE EXCEPTION 'invalid document request';
  END IF;
  INSERT INTO portal.document_requests(household_id,entity_id,title,description,due_at,created_by)
  VALUES (p_household_id,p_entity_id,trim(p_title),trim(COALESCE(p_description,'')),p_due_at,portal.current_user_id())
  RETURNING id INTO v_id;
  PERFORM portal.write_audit('document.request.created','document_request',v_id,p_household_id,jsonb_build_object('entity_id',p_entity_id));
  RETURN QUERY SELECT * FROM portal.document_requests WHERE id = v_id;
END
$$;

CREATE OR REPLACE FUNCTION portal.rpc_begin_upload(
  p_request_id uuid,
  p_filename text,
  p_content_type text,
  p_size bigint,
  p_idempotency_key text
)
RETURNS TABLE(document_id uuid, upload_id uuid, household_id uuid, object_key text, state portal.upload_state)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
DECLARE v_request portal.document_requests%ROWTYPE; v_document_id uuid; v_upload_id uuid; v_key text; v_existing portal.uploads%ROWTYPE;
BEGIN
  SELECT * INTO v_existing FROM portal.uploads
  WHERE created_by = portal.current_user_id() AND idempotency_key = p_idempotency_key;
  IF FOUND THEN
    RETURN QUERY SELECT v_existing.document_id,v_existing.id,v_existing.household_id,v_existing.object_key,v_existing.state;
    RETURN;
  END IF;
  SELECT * INTO v_request FROM portal.document_requests
  WHERE id = p_request_id AND deleted_at IS NULL FOR UPDATE;
  IF NOT FOUND OR NOT portal.can_entity(v_request.household_id,v_request.entity_id) THEN RAISE EXCEPTION 'request not found'; END IF;
  IF p_size NOT BETWEEN 1 AND 26214400 THEN RAISE EXCEPTION 'size outside policy'; END IF;
  IF p_content_type NOT IN ('application/pdf','image/jpeg','image/png','text/plain','text/csv','application/csv') THEN
    RAISE EXCEPTION 'content type outside policy';
  END IF;
  IF length(p_filename) NOT BETWEEN 1 AND 180 OR p_filename ~ '[\\/[:cntrl:]]'
     OR lower(substring(p_filename FROM '\.[^.]+$')) NOT IN ('.pdf','.jpg','.jpeg','.png','.txt','.csv') THEN
    RAISE EXCEPTION 'filename outside policy';
  END IF;
  IF p_idempotency_key !~ '^[A-Za-z0-9._:-]{8,128}$' THEN RAISE EXCEPTION 'invalid idempotency key'; END IF;
  v_document_id := gen_random_uuid(); v_upload_id := gen_random_uuid();
  v_key := format('quarantine/%s/%s/%s',v_request.household_id,v_document_id,gen_random_uuid());
  INSERT INTO portal.documents(
    id,household_id,entity_id,request_id,uploaded_by,original_filename,declared_content_type,quarantine_key,state
  ) VALUES (
    v_document_id,v_request.household_id,v_request.entity_id,v_request.id,portal.current_user_id(),p_filename,p_content_type,v_key,'uploading'
  );
  INSERT INTO portal.uploads(
    id,document_id,household_id,object_key,declared_size,idempotency_key,state,created_by
  ) VALUES (
    v_upload_id,v_document_id,v_request.household_id,v_key,p_size,p_idempotency_key,'initializing',portal.current_user_id()
  );
  UPDATE portal.document_requests SET status='uploading',updated_at=clock_timestamp() WHERE id=v_request.id;
  RETURN QUERY SELECT v_document_id,v_upload_id,v_request.household_id,v_key,'initializing'::portal.upload_state;
END
$$;

CREATE OR REPLACE FUNCTION portal.rpc_attach_multipart(p_upload_id uuid, p_multipart_upload_id text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
BEGIN
  UPDATE portal.uploads SET multipart_upload_id=p_multipart_upload_id,state='open',updated_at=clock_timestamp()
  WHERE id=p_upload_id AND created_by=portal.current_user_id() AND state='initializing' AND expires_at>clock_timestamp();
  IF NOT FOUND THEN RAISE EXCEPTION 'upload not attachable'; END IF;
END
$$;

CREATE OR REPLACE FUNCTION portal.rpc_get_upload_for_part(p_upload_id uuid, p_part_number integer)
RETURNS TABLE(upload_id uuid, household_id uuid, object_key text, multipart_upload_id text, declared_size bigint, uploaded_bytes bigint, state portal.upload_state)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
BEGIN
  IF p_part_number NOT BETWEEN 1 AND 10000 THEN RAISE EXCEPTION 'invalid part number'; END IF;
  RETURN QUERY SELECT u.id,u.household_id,u.object_key,u.multipart_upload_id,u.declared_size,u.uploaded_bytes,u.state
  FROM portal.uploads u
  WHERE u.id=p_upload_id AND u.created_by=portal.current_user_id()
    AND portal.can_household(u.household_id) AND u.state='open' AND u.expires_at>clock_timestamp();
  IF NOT FOUND THEN RAISE EXCEPTION 'upload unavailable'; END IF;
END
$$;

CREATE OR REPLACE FUNCTION portal.rpc_record_upload_part(p_upload_id uuid, p_part_number integer, p_etag text, p_size integer)
RETURNS TABLE(etag text, uploaded_bytes bigint, declared_size bigint, percent integer)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
DECLARE v_upload portal.uploads%ROWTYPE; v_total bigint;
BEGIN
  SELECT * INTO v_upload FROM portal.uploads u
  WHERE u.id=p_upload_id AND u.created_by=portal.current_user_id() AND u.state='open' AND u.expires_at>clock_timestamp()
  FOR UPDATE;
  IF NOT FOUND OR NOT portal.can_household(v_upload.household_id) THEN RAISE EXCEPTION 'upload unavailable'; END IF;
  IF p_part_number NOT BETWEEN 1 AND 10000 OR p_size NOT BETWEEN 1 AND 8388608 OR length(p_etag) NOT BETWEEN 1 AND 200 THEN
    RAISE EXCEPTION 'invalid part';
  END IF;
  INSERT INTO portal.upload_parts(upload_id,part_number,etag,size_bytes)
  VALUES (p_upload_id,p_part_number,p_etag,p_size)
  ON CONFLICT (upload_id,part_number) DO UPDATE SET etag=EXCLUDED.etag,size_bytes=EXCLUDED.size_bytes,recorded_at=clock_timestamp();
  SELECT COALESCE(sum(size_bytes),0) INTO v_total FROM portal.upload_parts WHERE upload_id=p_upload_id;
  IF v_total > v_upload.declared_size OR v_total > 26214400 THEN RAISE EXCEPTION 'uploaded bytes exceed policy'; END IF;
  UPDATE portal.uploads SET uploaded_bytes=v_total,updated_at=clock_timestamp() WHERE id=p_upload_id;
  RETURN QUERY SELECT p_etag,v_total,v_upload.declared_size,floor((v_total::numeric/v_upload.declared_size)*100)::integer;
END
$$;

CREATE OR REPLACE FUNCTION portal.rpc_get_upload(p_upload_id uuid)
RETURNS TABLE(
  upload_id uuid, document_id uuid, household_id uuid, object_key text, multipart_upload_id text,
  declared_size bigint, uploaded_bytes bigint, state portal.upload_state, expires_at timestamptz
)
LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
  SELECT u.id,u.document_id,u.household_id,u.object_key,u.multipart_upload_id,
         u.declared_size,u.uploaded_bytes,u.state,u.expires_at
  FROM portal.uploads u
  WHERE u.id=p_upload_id AND u.created_by=portal.current_user_id() AND portal.can_household(u.household_id)
$$;

CREATE OR REPLACE FUNCTION portal.rpc_complete_upload(p_upload_id uuid, p_authoritative_size bigint, p_authoritative_sha256 text)
RETURNS TABLE(document_id uuid, state portal.document_state, duplicate_of uuid, authoritative_size bigint, authoritative_sha256 text)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
DECLARE v_upload portal.uploads%ROWTYPE; v_document portal.documents%ROWTYPE; v_parts bigint; v_duplicate uuid;
BEGIN
  SELECT * INTO v_upload FROM portal.uploads u
  WHERE u.id=p_upload_id AND u.created_by=portal.current_user_id() AND u.state='open' AND u.expires_at>clock_timestamp()
  FOR UPDATE;
  IF NOT FOUND OR NOT portal.can_household(v_upload.household_id) THEN RAISE EXCEPTION 'upload unavailable'; END IF;
  SELECT COALESCE(sum(size_bytes),0) INTO v_parts FROM portal.upload_parts WHERE upload_id=p_upload_id;
  IF p_authoritative_size<>v_upload.declared_size OR p_authoritative_size<>v_parts
     OR p_authoritative_size NOT BETWEEN 1 AND 26214400 OR p_authoritative_sha256 !~ '^[0-9a-f]{64}$' THEN
    UPDATE portal.uploads SET state='aborted',updated_at=clock_timestamp() WHERE id=p_upload_id;
    UPDATE portal.documents SET state='rejected',review_note='authoritative size/hash validation failed',revision=revision+1,updated_at=clock_timestamp()
      WHERE id=v_upload.document_id;
    RAISE EXCEPTION 'authoritative upload validation failed';
  END IF;
  SELECT * INTO v_document FROM portal.documents WHERE id=v_upload.document_id FOR UPDATE;
  SELECT d.id INTO v_duplicate FROM portal.documents d
  WHERE d.id<>v_document.id AND d.household_id=v_document.household_id
    AND d.authoritative_sha256=p_authoritative_sha256 AND d.authoritative_size=p_authoritative_size
    AND d.state IN ('ready_for_review','accepted') AND d.deleted_at IS NULL
  ORDER BY d.created_at LIMIT 1;
  IF v_duplicate IS NOT NULL THEN
    UPDATE portal.documents SET authoritative_size=p_authoritative_size,authoritative_sha256=p_authoritative_sha256,
      state='duplicate',duplicate_of=v_duplicate,revision=revision+1,updated_at=clock_timestamp()
    WHERE id=v_document.id;
    UPDATE portal.uploads SET state='complete',uploaded_bytes=p_authoritative_size,updated_at=clock_timestamp() WHERE id=p_upload_id;
    INSERT INTO portal.object_delete_jobs(document_id,final_state) VALUES (v_document.id,'duplicate')
    ON CONFLICT (document_id) DO UPDATE SET final_state='duplicate',available_at=clock_timestamp(),completed_at=NULL;
    PERFORM portal.append_receipt(v_document.household_id,v_document.id,'document.duplicate_detected',portal.current_user_id()::text,
      jsonb_build_object('duplicate_of',v_duplicate,'sha256',p_authoritative_sha256,'size',p_authoritative_size));
    RETURN QUERY SELECT v_document.id,'duplicate'::portal.document_state,v_duplicate,p_authoritative_size,p_authoritative_sha256;
    RETURN;
  END IF;
  UPDATE portal.documents SET authoritative_size=p_authoritative_size,authoritative_sha256=p_authoritative_sha256,
    state='quarantined',revision=revision+1,updated_at=clock_timestamp()
  WHERE id=v_document.id;
  UPDATE portal.uploads SET state='scan_queued',uploaded_bytes=p_authoritative_size,updated_at=clock_timestamp() WHERE id=p_upload_id;
  UPDATE portal.document_requests SET status='quarantined',updated_at=clock_timestamp() WHERE id=v_document.request_id;
  INSERT INTO portal.scan_jobs(document_id) VALUES (v_document.id);
  INSERT INTO portal.outbox(channel,topic,aggregate_id,payload)
  VALUES ('worker','document.scan_requested',v_document.id,jsonb_build_object('document_id',v_document.id,'quarantine_key',v_document.quarantine_key));
  RETURN QUERY SELECT v_document.id,'quarantined'::portal.document_state,NULL::uuid,p_authoritative_size,p_authoritative_sha256;
END
$$;

CREATE OR REPLACE FUNCTION portal.rpc_abort_upload(p_upload_id uuid, p_reason text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
DECLARE v_document_id uuid;
BEGIN
  UPDATE portal.uploads SET state='aborted',updated_at=clock_timestamp()
  WHERE id=p_upload_id AND created_by=portal.current_user_id() AND state IN ('initializing','open')
  RETURNING document_id INTO v_document_id;
  IF v_document_id IS NOT NULL THEN
    UPDATE portal.documents SET state='rejected',review_note=left(p_reason,500),revision=revision+1,updated_at=clock_timestamp()
    WHERE id=v_document_id;
  END IF;
END
$$;

CREATE OR REPLACE FUNCTION portal.rpc_open_support_request(p_message text)
RETURNS SETOF portal.support_requests
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
DECLARE v_household_id uuid; v_id uuid;
BEGIN
  IF length(trim(p_message)) NOT BETWEEN 1 AND 500 THEN RAISE EXCEPTION 'invalid support message'; END IF;
  SELECT m.household_id INTO v_household_id FROM portal.memberships m
  WHERE m.user_id=portal.current_user_id() AND m.role='client' AND m.revoked_at IS NULL
  ORDER BY m.created_at LIMIT 1;
  IF NOT FOUND THEN RAISE EXCEPTION 'client membership required'; END IF;
  INSERT INTO portal.support_requests(household_id,created_by,message)
  VALUES (v_household_id,portal.current_user_id(),trim(p_message)) RETURNING id INTO v_id;
  INSERT INTO portal.outbox(channel,topic,aggregate_id,payload)
  VALUES ('advisor_queue','portal.support.requested',v_id,jsonb_build_object('support_request_id',v_id,'household_id',v_household_id));
  RETURN QUERY SELECT * FROM portal.support_requests WHERE id=v_id;
END
$$;

CREATE OR REPLACE FUNCTION portal.rpc_review_document(p_document_id uuid, p_decision text, p_note text, p_expected_revision integer)
RETURNS SETOF portal.documents
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
DECLARE v_document portal.documents%ROWTYPE; v_new_state portal.document_state;
BEGIN
  SELECT * INTO v_document FROM portal.documents WHERE id=p_document_id FOR UPDATE;
  IF NOT FOUND OR NOT portal.can_entity(v_document.household_id,v_document.entity_id)
     OR NOT portal.has_household_role(v_document.household_id,ARRAY['advisor','operations']::portal.portal_role[]) THEN
    RAISE EXCEPTION 'forbidden';
  END IF;
  IF v_document.revision<>p_expected_revision OR v_document.state NOT IN ('ready_for_review','needs_replacement') THEN RAISE EXCEPTION 'revision conflict'; END IF;
  v_new_state := CASE p_decision WHEN 'accept' THEN 'accepted' WHEN 'replace' THEN 'needs_replacement' WHEN 'reject' THEN 'rejected' ELSE NULL END;
  IF v_new_state IS NULL THEN RAISE EXCEPTION 'invalid decision'; END IF;
  UPDATE portal.documents SET state=v_new_state,review_note=left(COALESCE(p_note,''),1000),revision=revision+1,updated_at=clock_timestamp()
  WHERE id=p_document_id;
  UPDATE portal.document_requests SET status=CASE p_decision WHEN 'accept' THEN 'complete' WHEN 'replace' THEN 'missing' ELSE 'review' END,
    updated_at=clock_timestamp() WHERE id=v_document.request_id;
  PERFORM portal.append_receipt(v_document.household_id,v_document.id,'document.review.'||p_decision,portal.current_user_id()::text,
    jsonb_build_object('note',left(COALESCE(p_note,''),1000)));
  IF p_decision='accept' THEN
    INSERT INTO portal.outbox(channel,topic,aggregate_id,payload)
    VALUES ('mas_intake','mas.document.accepted',v_document.id,jsonb_build_object(
      'direction','outbound_only','document_id',v_document.id,'household_id',v_document.household_id,'entity_id',v_document.entity_id,
      'sha256',v_document.authoritative_sha256,'size',v_document.authoritative_size,'content_type',v_document.authoritative_content_type
    ));
  END IF;
  RETURN QUERY SELECT * FROM portal.documents WHERE id=p_document_id;
END
$$;

CREATE OR REPLACE FUNCTION portal.rpc_authorize_document_download(p_document_id uuid)
RETURNS TABLE(clean_key text,original_filename text,authoritative_sha256 text,authoritative_size bigint)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
DECLARE v_document portal.documents%ROWTYPE;
BEGIN
  SELECT * INTO v_document FROM portal.documents WHERE id=p_document_id;
  IF NOT FOUND OR NOT portal.can_entity(v_document.household_id,v_document.entity_id)
     OR NOT portal.has_household_role(v_document.household_id,ARRAY['advisor','operations']::portal.portal_role[])
     OR NOT portal.has_current_step_up() OR v_document.state NOT IN ('ready_for_review','accepted') OR v_document.clean_key IS NULL THEN
    RAISE EXCEPTION 'download forbidden';
  END IF;
  PERFORM portal.write_audit('document.download.authorized','document',v_document.id,v_document.household_id,
    jsonb_build_object('capability_ttl_seconds',60));
  RETURN QUERY SELECT v_document.clean_key,v_document.original_filename,v_document.authoritative_sha256::text,v_document.authoritative_size;
END
$$;

CREATE OR REPLACE FUNCTION portal.rpc_request_document_delete(p_document_id uuid, p_reason text, p_expected_revision integer)
RETURNS SETOF portal.documents
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, portal
AS $$
DECLARE v_document portal.documents%ROWTYPE;
BEGIN
  SELECT * INTO v_document FROM portal.documents WHERE id=p_document_id FOR UPDATE;
  IF NOT FOUND OR NOT portal.has_household_role(v_document.household_id,ARRAY['advisor']::portal.portal_role[])
     OR NOT portal.can_entity(v_document.household_id,v_document.entity_id) OR NOT portal.has_current_step_up() THEN RAISE EXCEPTION 'forbidden'; END IF;
  IF v_document.revision<>p_expected_revision OR v_document.state IN ('delete_pending','deleted') THEN RAISE EXCEPTION 'revision conflict'; END IF;
  UPDATE portal.documents SET state='delete_pending',review_note=left(p_reason,1000),revision=revision+1,updated_at=clock_timestamp() WHERE id=p_document_id;
  INSERT INTO portal.object_delete_jobs(document_id,final_state) VALUES (p_document_id,'deleted')
  ON CONFLICT (document_id) DO UPDATE SET final_state='deleted',available_at=clock_timestamp(),completed_at=NULL;
  PERFORM portal.append_receipt(v_document.household_id,v_document.id,'document.delete_requested',portal.current_user_id()::text,
    jsonb_build_object('reason',left(p_reason,1000),'previous_state',v_document.state));
  RETURN QUERY SELECT * FROM portal.documents WHERE id=p_document_id;
END
$$;

REVOKE ALL ON FUNCTION portal.append_receipt(uuid,uuid,text,text,jsonb) FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.rpc_create_document_request(uuid,uuid,text,text,timestamptz) FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.rpc_begin_upload(uuid,text,text,bigint,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.rpc_attach_multipart(uuid,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.rpc_get_upload_for_part(uuid,integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.rpc_record_upload_part(uuid,integer,text,integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.rpc_get_upload(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.rpc_complete_upload(uuid,bigint,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.rpc_abort_upload(uuid,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.rpc_open_support_request(text) FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.rpc_review_document(uuid,text,text,integer) FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.rpc_authorize_document_download(uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION portal.rpc_request_document_delete(uuid,text,integer) FROM PUBLIC;

GRANT EXECUTE ON FUNCTION portal.rpc_create_document_request(uuid,uuid,text,text,timestamptz) TO portal_api;
GRANT EXECUTE ON FUNCTION portal.rpc_begin_upload(uuid,text,text,bigint,text) TO portal_api;
GRANT EXECUTE ON FUNCTION portal.rpc_attach_multipart(uuid,text) TO portal_api;
GRANT EXECUTE ON FUNCTION portal.rpc_get_upload_for_part(uuid,integer) TO portal_api;
GRANT EXECUTE ON FUNCTION portal.rpc_record_upload_part(uuid,integer,text,integer) TO portal_api;
GRANT EXECUTE ON FUNCTION portal.rpc_get_upload(uuid) TO portal_api;
GRANT EXECUTE ON FUNCTION portal.rpc_complete_upload(uuid,bigint,text) TO portal_api;
GRANT EXECUTE ON FUNCTION portal.rpc_abort_upload(uuid,text) TO portal_api;
GRANT EXECUTE ON FUNCTION portal.rpc_open_support_request(text) TO portal_api;
GRANT EXECUTE ON FUNCTION portal.rpc_review_document(uuid,text,text,integer) TO portal_api;
GRANT EXECUTE ON FUNCTION portal.rpc_authorize_document_download(uuid) TO portal_api;
GRANT EXECUTE ON FUNCTION portal.rpc_request_document_delete(uuid,text,integer) TO portal_api;

COMMIT;
