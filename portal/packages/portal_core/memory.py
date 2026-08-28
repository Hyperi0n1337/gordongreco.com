from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any

from .errors import Conflict, NotFound
from .ids import new_id
from .models import (
    Approval,
    CashOperation,
    Document,
    DocumentRequest,
    Invitation,
    MagicLink,
    Membership,
    OutboxMessage,
    Receipt,
    RecoveryCode,
    RecalculationJob,
    Session,
    SupportRequest,
    TreasuryPolicyVersion,
    UploadSession,
    User,
)


class MemoryStore:
    """Deterministic in-memory repository used by security tests and local demos.

    Production uses PostgreSQL with the same invariants additionally enforced by
    constraints, RLS, immutable triggers, and SECURITY DEFINER RPCs.
    """

    def __init__(self) -> None:
        self.users: dict[str, User] = {}
        self.users_by_email: dict[str, str] = {}
        self.memberships: dict[str, Membership] = {}
        self.invitations: dict[str, Invitation] = {}
        self.magic_links: dict[str, MagicLink] = {}
        self.sessions: dict[str, Session] = {}
        self.recovery_codes: dict[str, RecoveryCode] = {}
        self.document_requests: dict[str, DocumentRequest] = {}
        self.documents: dict[str, Document] = {}
        self.uploads: dict[str, UploadSession] = {}
        self.receipts: list[Receipt] = []
        self.support_requests: dict[str, SupportRequest] = {}
        self.policies: dict[str, TreasuryPolicyVersion] = {}
        self.cash_operations: dict[str, CashOperation] = {}
        self.approvals: list[Approval] = []
        self.outbox: list[OutboxMessage] = []
        self.recalculations: list[RecalculationJob] = []
        self.idempotency: dict[tuple[str, str, str], str] = {}
        self.audit_events: list[dict[str, Any]] = []

    def add_user(self, user: User) -> None:
        if user.id in self.users or user.email in self.users_by_email:
            raise Conflict("user already exists")
        self.users[user.id] = user
        self.users_by_email[user.email] = user.id

    def find_user_by_email(self, email: str) -> User | None:
        user_id = self.users_by_email.get(email)
        return self.users.get(user_id) if user_id else None

    def active_memberships(self, user_id: str) -> list[Membership]:
        return [m for m in self.memberships.values() if m.user_id == user_id and m.revoked_at is None]

    def require_document_request(self, request_id: str) -> DocumentRequest:
        try:
            return self.document_requests[request_id]
        except KeyError as exc:
            raise NotFound("document request not found") from exc

    def require_document(self, document_id: str) -> Document:
        try:
            return self.documents[document_id]
        except KeyError as exc:
            raise NotFound("document not found") from exc

    def require_upload(self, upload_id: str) -> UploadSession:
        try:
            return self.uploads[upload_id]
        except KeyError as exc:
            raise NotFound("upload not found") from exc

    def require_policy(self, policy_id: str) -> TreasuryPolicyVersion:
        try:
            return self.policies[policy_id]
        except KeyError as exc:
            raise NotFound("treasury policy not found") from exc

    def require_cash_operation(self, operation_id: str) -> CashOperation:
        try:
            return self.cash_operations[operation_id]
        except KeyError as exc:
            raise NotFound("cash operation not found") from exc

    def approvals_for(self, workflow_type: str, workflow_id: str) -> list[Approval]:
        return [
            row
            for row in self.approvals
            if row.workflow_type == workflow_type and row.workflow_id == workflow_id
        ]

    def remember_idempotency(self, namespace: str, owner: str, key: str, object_id: str) -> None:
        composite = (namespace, owner, key)
        existing = self.idempotency.get(composite)
        if existing and existing != object_id:
            raise Conflict("idempotency key already used")
        self.idempotency[composite] = object_id

    def idempotent_object(self, namespace: str, owner: str, key: str) -> str | None:
        return self.idempotency.get((namespace, owner, key))

    def audit(self, *, at: datetime, actor_id: str, action: str, object_id: str, detail: dict[str, Any]) -> None:
        self.audit_events.append(
            {
                "id": new_id(),
                "at": at,
                "actor_id": actor_id,
                "action": action,
                "object_id": object_id,
                "detail": detail,
            }
        )


class MemoryObjectStore:
    """Private object-store stand-in. Keys are never user supplied."""

    def __init__(self) -> None:
        self._objects: dict[tuple[str, str], bytes] = {}
        self._multipart: dict[str, dict[int, bytes]] = {}
        self._multipart_meta: dict[str, tuple[str, str]] = {}

    def create_multipart(self, *, bucket: str, key: str) -> str:
        upload_id = new_id()
        self._multipart[upload_id] = {}
        self._multipart_meta[upload_id] = (bucket, key)
        return upload_id

    def put_part(self, upload_id: str, part_number: int, data: bytes) -> str:
        if upload_id not in self._multipart:
            raise NotFound("multipart upload not found")
        if part_number < 1 or part_number > 10_000:
            raise ValueError("invalid part number")
        self._multipart[upload_id][part_number] = bytes(data)
        import hashlib

        return hashlib.md5(data, usedforsecurity=False).hexdigest()  # S3-compatible test ETag only.

    def list_parts(self, upload_id: str) -> dict[int, int]:
        if upload_id not in self._multipart:
            raise NotFound("multipart upload not found")
        return {n: len(data) for n, data in self._multipart[upload_id].items()}

    def complete_multipart(self, upload_id: str, ordered_parts: list[int]) -> tuple[str, str, int]:
        if upload_id not in self._multipart:
            raise NotFound("multipart upload not found")
        parts = self._multipart[upload_id]
        if not ordered_parts or ordered_parts != sorted(set(ordered_parts)):
            raise Conflict("parts must be unique and ordered")
        try:
            body = b"".join(parts[n] for n in ordered_parts)
        except KeyError as exc:
            raise Conflict("missing multipart part") from exc
        bucket, key = self._multipart_meta[upload_id]
        self._objects[(bucket, key)] = body
        del self._multipart[upload_id]
        del self._multipart_meta[upload_id]
        return bucket, key, len(body)

    def abort_multipart(self, upload_id: str) -> None:
        self._multipart.pop(upload_id, None)
        self._multipart_meta.pop(upload_id, None)

    def get(self, *, bucket: str, key: str) -> bytes:
        try:
            return self._objects[(bucket, key)]
        except KeyError as exc:
            raise NotFound("object not found") from exc

    def put(self, *, bucket: str, key: str, data: bytes) -> None:
        self._objects[(bucket, key)] = bytes(data)

    def copy(self, *, source_bucket: str, source_key: str, target_bucket: str, target_key: str) -> None:
        self.put(bucket=target_bucket, key=target_key, data=self.get(bucket=source_bucket, key=source_key))

    def delete(self, *, bucket: str, key: str) -> None:
        self._objects.pop((bucket, key), None)

    def exists(self, *, bucket: str, key: str) -> bool:
        return (bucket, key) in self._objects
