from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class MagicLinkRequest(StrictModel):
    email: str = Field(max_length=254)


class MagicLinkConsume(StrictModel):
    token: str = Field(min_length=32, max_length=256)


class TotpCode(StrictModel):
    code: str = Field(pattern=r"^\d{6}$")


class RecoveryCodeInput(StrictModel):
    recovery_code: str = Field(min_length=10, max_length=64)


class InviteInput(StrictModel):
    email: str = Field(max_length=254)
    display_name: str = Field(min_length=1, max_length=120)
    household_id: str
    role: Literal["client", "advisor", "operations"] = "client"
    entity_ids: list[str] = Field(default_factory=list, max_length=100)
    expires_in_days: int = Field(default=7, ge=1, le=30)


class RevokeInput(StrictModel):
    user_id: str
    household_id: str
    reason: str = Field(min_length=1, max_length=240)


class DocumentRequestInput(StrictModel):
    household_id: str
    entity_id: str | None = None
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)
    due_at: datetime | None = None


class UploadBeginInput(StrictModel):
    request_id: str
    filename: str = Field(min_length=1, max_length=180)
    content_type: str = Field(min_length=3, max_length=100)
    size: int = Field(gt=0, le=25 * 1024 * 1024)
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9._:-]{8,128}$")


class UploadCompleteInput(StrictModel):
    parts: list[dict[str, Any]] = Field(min_length=1, max_length=10000)

    @field_validator("parts")
    @classmethod
    def validate_parts(cls, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        numbers = [int(row.get("part_number", 0)) for row in rows]
        if numbers != sorted(set(numbers)) or numbers[0] != 1:
            raise ValueError("part numbers must be unique, ordered, and start at 1")
        for row in rows:
            if not str(row.get("etag", "")) or len(str(row["etag"])) > 200:
                raise ValueError("each part requires an ETag")
        return rows


class ReviewInput(StrictModel):
    decision: Literal["accept", "replace", "reject"]
    note: str = Field(default="", max_length=1000)
    expected_revision: int = Field(ge=1)


class DeleteInput(StrictModel):
    reason: str = Field(min_length=1, max_length=1000)
    expected_revision: int = Field(ge=1)


class SupportInput(StrictModel):
    message: str = Field(min_length=1, max_length=500)


class PolicyInput(StrictModel):
    household_id: str
    base_version_id: str | None = None
    effective_at: datetime
    terms: dict[str, Any]
    signer_user_ids: list[str] = Field(min_length=1, max_length=20)
    approval_threshold: int = Field(ge=1, le=20)
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9._:-]{8,128}$")


class ApprovalInput(StrictModel):
    expected_revision: int = Field(ge=1)


class CashOperationInput(StrictModel):
    household_id: str
    entity_id: str | None = None
    policy_version_id: str
    operation_type: Literal[
        "operating_reserve_adjustment",
        "planned_tax_payment_reserve",
        "same_entity_liquidity_allocation",
        "external_cash_need_notice",
    ]
    amount_minor: int = Field(gt=0)
    currency: str = Field(pattern=r"^[A-Za-z]{3}$")
    requested_effective_at: datetime
    rationale: str = Field(min_length=1, max_length=2000)
    conflict_key: str = Field(min_length=1, max_length=160)
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9._:-]{8,128}$")
