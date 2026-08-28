import hashlib

import pytest

from conftest import ENTITY_SHARED, HH_A
from portal_core.errors import Conflict, Forbidden, IntegrityFailure, ScannerUnavailable
from portal_core.models import DocumentState
from portal_core.scanning import ScanPipeline


class Magic:
    def __init__(self, mime): self.mime = mime
    def mime_type(self, data): return self.mime


class Malware:
    def __init__(self, result="clean", fail=False): self.result, self.fail = result, fail
    def scan(self, data):
        if self.fail: raise RuntimeError("clamav unavailable")
        return self.result


class Pdf:
    def validate(self, data): return "qpdf --check passed"


def scanner(mime="text/plain", result="clean", fail=False):
    return ScanPipeline(Magic(mime), Malware(result, fail), Pdf())


def request(upload_service, actor_factory):
    return upload_service.create_document_request(
        advisor=actor_factory("advisor-a"), household_id=HH_A, entity_id=ENTITY_SHARED,
        title="Fictional statement", description="Synthetic test request", due_at=None,
    )


def begin(upload_service, actor_factory, req, body, key="upload-test-0001", filename="statement.txt", mime="text/plain"):
    return upload_service.begin_upload(
        actor=actor_factory("client-a"), request_id=req.id, filename=filename,
        declared_content_type=mime, declared_size=len(body), idempotency_key=key,
    )


def put(upload_service, actor, start, part_number, body):
    cap = upload_service.sign_upload_part(actor=actor, upload_id=start.upload.id, part_number=part_number)
    return upload_service.upload_part(
        actor=actor, upload_id=start.upload.id, part_number=part_number, capability=cap.token, data=body
    )


def complete_clean(upload_service, actor_factory, req, body=b"fictional statement", key="upload-test-0001"):
    actor = actor_factory("client-a")
    start = begin(upload_service, actor_factory, req, body, key)
    put(upload_service, actor, start, 1, body)
    document = upload_service.complete_upload(actor=actor, upload_id=start.upload.id, ordered_parts=[1])
    upload_service.scan_document(document_id=document.id, scanner=scanner())
    return document


def test_interrupted_upload_resume_authoritative_hash_and_clean_copy(upload_service, actor_factory, objects):
    req = request(upload_service, actor_factory)
    body = b"part-one|part-two"
    actor = actor_factory("client-a")
    start = begin(upload_service, actor_factory, req, body)
    put(upload_service, actor, start, 1, b"part-one|")
    resumed = upload_service.resume_upload(actor=actor, upload_id=start.upload.id)
    assert resumed["parts"] == {1: 9} and resumed["uploaded_bytes"] == 9
    put(upload_service, actor, start, 2, b"part-two")
    document = upload_service.complete_upload(actor=actor, upload_id=start.upload.id, ordered_parts=[1, 2])
    assert document.state is DocumentState.QUARANTINED
    assert document.authoritative_sha256 == hashlib.sha256(body).hexdigest()
    upload_service.scan_document(document_id=document.id, scanner=scanner())
    assert document.state is DocumentState.READY_FOR_REVIEW
    assert objects.exists(bucket="clean", key=document.clean_key)
    assert not objects.exists(bucket="quarantine", key=document.quarantine_key)
    assert any(r.event_type == "document.clean_stored" for r in upload_service.store.receipts)


def test_upload_idempotency_and_owner_isolation(upload_service, actor_factory):
    req = request(upload_service, actor_factory)
    body = b"fictional"
    first = begin(upload_service, actor_factory, req, body, "idempotent-upload-001")
    second = begin(upload_service, actor_factory, req, body, "idempotent-upload-001")
    assert first.upload.id == second.upload.id
    with pytest.raises(Forbidden):
        upload_service.sign_upload_part(actor=actor_factory("client-a2"), upload_id=first.upload.id, part_number=1)


def test_capability_tamper_and_authoritative_size_mismatch(upload_service, actor_factory):
    req = request(upload_service, actor_factory)
    actor = actor_factory("client-a")
    start = begin(upload_service, actor_factory, req, b"12345")
    cap = upload_service.sign_upload_part(actor=actor, upload_id=start.upload.id, part_number=1)
    with pytest.raises(Forbidden):
        upload_service.upload_part(actor=actor, upload_id=start.upload.id, part_number=2, capability=cap.token, data=b"12345")
    upload_service.upload_part(actor=actor, upload_id=start.upload.id, part_number=1, capability=cap.token, data=b"1234")
    with pytest.raises(IntegrityFailure):
        upload_service.complete_upload(actor=actor, upload_id=start.upload.id, ordered_parts=[1])
    assert start.document.state is DocumentState.REJECTED


def test_duplicate_handling_deletes_redundant_quarantine_object(upload_service, actor_factory, objects):
    req = request(upload_service, actor_factory)
    body = b"duplicate fictional content"
    first = complete_clean(upload_service, actor_factory, req, body, "duplicate-upload-001")
    upload_service.review_document(advisor=actor_factory("advisor-a"), document_id=first.id, decision="accept")
    actor = actor_factory("client-a")
    second = begin(upload_service, actor_factory, req, body, "duplicate-upload-002")
    put(upload_service, actor, second, 1, body)
    duplicate = upload_service.complete_upload(actor=actor, upload_id=second.upload.id, ordered_parts=[1])
    assert duplicate.state is DocumentState.DUPLICATE and duplicate.duplicate_of == first.id
    assert not objects.exists(bucket="quarantine", key=duplicate.quarantine_key)


def test_scan_failures_stay_quarantined_and_malware_is_rejected(upload_service, actor_factory):
    req = request(upload_service, actor_factory)
    actor = actor_factory("client-a")
    start = begin(upload_service, actor_factory, req, b"fictional", "scan-fail-upload-001")
    put(upload_service, actor, start, 1, b"fictional")
    doc = upload_service.complete_upload(actor=actor, upload_id=start.upload.id, ordered_parts=[1])
    with pytest.raises(ScannerUnavailable):
        upload_service.scan_document(document_id=doc.id, scanner=scanner(fail=True))
    assert doc.state is DocumentState.QUARANTINED
    result = upload_service.scan_document(document_id=doc.id, scanner=scanner(result="Eicar-Test-Signature"))
    assert not result.clean and doc.state is DocumentState.REJECTED


def test_review_download_delete_receipt_and_outbound_only_intake(upload_service, actor_factory, objects):
    req = request(upload_service, actor_factory)
    doc = complete_clean(upload_service, actor_factory, req, b"reviewable", "review-upload-001")
    advisor = actor_factory("advisor-a")
    accepted = upload_service.review_document(advisor=advisor, document_id=doc.id, decision="accept", note="Accepted")
    assert accepted.state is DocumentState.ACCEPTED and req.status == "complete"
    envelope = next(m for m in upload_service.store.outbox if m.topic == "mas.document.accepted")
    assert envelope.payload["direction"] == "outbound_only"
    cap = upload_service.sign_download(advisor=advisor, document_id=doc.id)
    assert cap.expires_at > upload_service.clock.now()
    key = doc.clean_key
    deleted = upload_service.delete_document(advisor=advisor, document_id=doc.id, reason="fictional retention test")
    assert deleted.state is DocumentState.DELETED and not objects.exists(bucket="clean", key=key)
    assert {r.event_type for r in upload_service.store.receipts} >= {"document.clean_stored", "document.review.accept", "document.deleted"}


def test_single_support_action_is_scoped_to_client_household(upload_service, actor_factory):
    row = upload_service.open_support_request(client=actor_factory("client-a"), message="Please help with this test upload.")
    assert row.household_id == HH_A and row.category == "portal_document_support"
    assert any(m.topic == "portal.support.requested" for m in upload_service.store.outbox)
