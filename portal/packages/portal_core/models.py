from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class Role(StrEnum):
    CLIENT = "client"
    ADVISOR = "advisor"
    OPERATIONS = "operations"
    WORKER = "worker"


class DocumentState(StrEnum):
    MISSING = "missing"
    UPLOADING = "uploading"
    QUARANTINED = "quarantined"
    SCANNING = "scanning"
    READY_FOR_REVIEW = "ready_for_review"
    ACCEPTED = "accepted"
    NEEDS_REPLACEMENT = "needs_replacement"
    DUPLICATE = "duplicate"
    REJECTED = "rejected"
    DELETED = "deleted"


class UploadState(StrEnum):
    OPEN = "open"
    OBJECT_COMPLETE = "object_complete"
    HASHED = "hashed"
    SCAN_QUEUED = "scan_queued"
    COMPLETE = "complete"
    ABORTED = "aborted"
    EXPIRED = "expired"


class PolicyState(StrEnum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class CashOperationState(StrEnum):
    PENDING_APPROVAL = "pending_approval"
    APPROVED_FOR_INTAKE = "approved_for_intake"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


@dataclass
class User:
    id: str
    email: str
    display_name: str
    active: bool = False
    revoked_at: datetime | None = None
    auth_epoch: int = 0
    totp_ciphertext: str | None = None
    totp_confirmed_at: datetime | None = None
    totp_last_counter: int = -1


@dataclass
class Membership:
    id: str
    user_id: str
    household_id: str
    role: Role
    entity_ids: frozenset[str] = field(default_factory=frozenset)
    revoked_at: datetime | None = None


@dataclass
class ActorContext:
    user_id: str
    email: str
    display_name: str
    role: Role
    household_ids: frozenset[str]
    entity_ids: frozenset[str]
    session_id: str
    auth_level: int
    step_up_until: datetime | None
    entity_scope: frozenset[tuple[str, str]] = field(default_factory=frozenset)
    role_scope: frozenset[tuple[str, Role]] = field(default_factory=frozenset)

    def has_step_up(self, now: datetime) -> bool:
        return self.auth_level >= 2 and self.step_up_until is not None and self.step_up_until > now


@dataclass
class Invitation:
    id: str
    user_id: str
    token_digest: str
    expires_at: datetime
    created_by: str
    created_at: datetime
    consumed_at: datetime | None = None
    revoked_at: datetime | None = None


@dataclass
class MagicLink:
    id: str
    user_id: str
    token_digest: str
    expires_at: datetime
    created_at: datetime
    consumed_at: datetime | None = None
    revoked_at: datetime | None = None


@dataclass
class Session:
    id: str
    user_id: str
    token_digest: str
    auth_epoch: int
    created_at: datetime
    expires_at: datetime
    auth_level: int = 1
    step_up_until: datetime | None = None
    revoked_at: datetime | None = None
    last_seen_at: datetime | None = None


@dataclass
class RecoveryCode:
    id: str
    user_id: str
    code_digest: str
    created_at: datetime
    consumed_at: datetime | None = None
    revoked_at: datetime | None = None


@dataclass
class DocumentRequest:
    id: str
    household_id: str
    entity_id: str | None
    title: str
    description: str
    due_at: datetime | None
    created_by: str
    created_at: datetime
    status: str = "missing"


@dataclass
class Document:
    id: str
    household_id: str
    entity_id: str | None
    request_id: str
    uploaded_by: str
    original_filename: str
    declared_content_type: str
    authoritative_content_type: str | None
    authoritative_size: int | None
    authoritative_sha256: str | None
    quarantine_key: str
    clean_key: str | None
    state: DocumentState
    created_at: datetime
    updated_at: datetime
    duplicate_of: str | None = None
    review_note: str | None = None
    deleted_at: datetime | None = None


@dataclass
class UploadSession:
    id: str
    document_id: str
    household_id: str
    object_key: str
    declared_size: int
    multipart_upload_id: str
    idempotency_key: str
    created_at: datetime
    expires_at: datetime
    state: UploadState = UploadState.OPEN
    uploaded_bytes: int = 0
    completed_parts: dict[int, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ScanFinding:
    control: str
    result: str
    detail: str


@dataclass(frozen=True)
class ScanResult:
    clean: bool
    mime_type: str
    findings: tuple[ScanFinding, ...]
    reason: str = ""


@dataclass(frozen=True)
class Receipt:
    id: str
    household_id: str
    document_id: str | None
    event_type: str
    event_at: datetime
    actor_id: str
    payload: dict[str, Any]
    receipt_sha256: str


@dataclass
class SupportRequest:
    id: str
    household_id: str
    created_by: str
    category: str
    message: str
    created_at: datetime
    status: str = "open"


@dataclass
class TreasuryPolicyVersion:
    id: str
    household_id: str
    version: int
    base_version_id: str | None
    effective_at: datetime
    terms: dict[str, Any]
    signer_user_ids: tuple[str, ...]
    approval_threshold: int
    state: PolicyState
    created_by: str
    created_at: datetime
    approved_at: datetime | None = None
    revision: int = 1
    idempotency_key: str = ""


@dataclass
class CashOperation:
    id: str
    household_id: str
    entity_id: str | None
    policy_version_id: str
    operation_type: str
    amount_minor: int
    currency: str
    requested_effective_at: datetime
    rationale: str
    conflict_key: str
    signer_user_ids: tuple[str, ...]
    approval_threshold: int
    state: CashOperationState
    created_by: str
    created_at: datetime
    idempotency_key: str
    revision: int = 1
    approved_at: datetime | None = None
    execution_state: str = "not_executable"


@dataclass(frozen=True)
class Approval:
    id: str
    workflow_type: str
    workflow_id: str
    signer_user_id: str
    approved_at: datetime
    workflow_revision: int


@dataclass
class OutboxMessage:
    id: str
    channel: str
    topic: str
    aggregate_id: str
    payload: dict[str, Any]
    created_at: datetime
    available_at: datetime
    delivered_at: datetime | None = None
    attempts: int = 0
    last_error: str | None = None


@dataclass
class RecalculationJob:
    id: str
    household_id: str
    reason: str
    source_id: str
    requested_at: datetime
    completed_at: datetime | None = None
