import hashlib
import json

from conftest import ENTITY_SHARED, HH_A


def test_receipt_hash_is_reproducible_and_receipts_are_append_only_in_core(upload_service, actor_factory):
    req = upload_service.create_document_request(
        advisor=actor_factory("advisor-a"), household_id=HH_A, entity_id=ENTITY_SHARED,
        title="Receipt test", description="fictional", due_at=None)
    body = b"receipt test body"
    client = actor_factory("client-a")
    start = upload_service.begin_upload(actor=client, request_id=req.id, filename="receipt.txt",
        declared_content_type="text/plain", declared_size=len(body), idempotency_key="receipt-upload-test-001")
    cap = upload_service.sign_upload_part(actor=client, upload_id=start.upload.id, part_number=1)
    upload_service.upload_part(actor=client, upload_id=start.upload.id, part_number=1, capability=cap.token, data=body)
    doc = upload_service.complete_upload(actor=client, upload_id=start.upload.id, ordered_parts=[1])
    # Trigger the deterministic duplicate receipt with a prior accepted object would require scan adapters;
    # directly exercise the same canonical hash contract through the service's append-only helper.
    receipt = upload_service._receipt(document=doc, event_type="document.test_receipt", actor_id=client.user_id,
        payload={"sha256": doc.authoritative_sha256, "size": doc.authoritative_size})
    canonical = json.dumps({"id":receipt.id,"household_id":receipt.household_id,"document_id":receipt.document_id,
        "event_type":receipt.event_type,"event_at":receipt.event_at.isoformat(),"actor_id":receipt.actor_id,
        "payload":receipt.payload}, sort_keys=True, separators=(",", ":"), default=str).encode()
    assert receipt.receipt_sha256 == hashlib.sha256(canonical).hexdigest()
    assert upload_service.store.receipts[-1] is receipt
