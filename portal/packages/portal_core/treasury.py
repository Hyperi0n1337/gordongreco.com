from __future__ import annotations

from datetime import timedelta
from typing import Any, Iterable

from .clock import Clock
from .errors import Conflict, Forbidden, ValidationError
from .ids import new_id
from .memory import MemoryStore
from .models import (
    ActorContext,
    Approval,
    CashOperation,
    CashOperationState,
    OutboxMessage,
    PolicyState,
    RecalculationJob,
    Role,
    TreasuryPolicyVersion,
)
from .scope import require_entity, require_household, require_role, require_step_up


class TreasuryService:
    """Approval and intake workflow only; never executes a trade or money movement."""

    ALLOWED_OPERATION_TYPES = {
        "operating_reserve_adjustment",
        "planned_tax_payment_reserve",
        "same_entity_liquidity_allocation",
        "external_cash_need_notice",
    }

    def __init__(self, *, store: MemoryStore, clock: Clock, minimum_future_delay: timedelta = timedelta(minutes=5)) -> None:
        self.store = store
        self.clock = clock
        self.minimum_future_delay = minimum_future_delay

    def _validate_signers(self, *, household_id: str, signer_user_ids: Iterable[str], threshold: int) -> tuple[str, ...]:
        signers = tuple(dict.fromkeys(signer_user_ids))
        if not signers or threshold < 1 or threshold > len(signers):
            raise ValidationError("invalid signer set or threshold")
        active_by_user = {
            membership.user_id: membership
            for membership in self.store.memberships.values()
            if membership.household_id == household_id and membership.revoked_at is None
        }
        if any(signer not in active_by_user for signer in signers):
            raise ValidationError("every signer must have an active household membership")
        if not any(active_by_user[signer].role is Role.ADVISOR for signer in signers):
            raise ValidationError("at least one designated signer must be an advisor")
        return signers

    @staticmethod
    def _validate_terms(terms: dict[str, Any]) -> dict[str, Any]:
        required = {
            "currency",
            "minimum_operating_reserve_minor",
            "cash_operation_limit_minor",
            "permitted_operation_types",
        }
        if set(terms) < required:
            raise ValidationError(f"policy terms require {sorted(required)}")
        currency = str(terms["currency"]).upper()
        if len(currency) != 3 or not currency.isalpha():
            raise ValidationError("policy currency must be an ISO-like 3-letter code")
        reserve = int(terms["minimum_operating_reserve_minor"])
        limit = int(terms["cash_operation_limit_minor"])
        permitted = tuple(dict.fromkeys(str(item) for item in terms["permitted_operation_types"]))
        if reserve < 0 or limit <= 0:
            raise ValidationError("policy monetary limits are invalid")
        if not permitted or any(item not in TreasuryService.ALLOWED_OPERATION_TYPES for item in permitted):
            raise ValidationError("policy contains unsupported operation types")
        return {
            "currency": currency,
            "minimum_operating_reserve_minor": reserve,
            "cash_operation_limit_minor": limit,
            "permitted_operation_types": list(permitted),
            "notes": str(terms.get("notes", ""))[:2_000],
        }

    def propose_initial_policy(
        self,
        *,
        advisor: ActorContext,
        household_id: str,
        effective_at: object,
        terms: dict[str, Any],
        signer_user_ids: Iterable[str],
        approval_threshold: int,
        idempotency_key: str,
    ) -> TreasuryPolicyVersion:
        now = self.clock.now()
        require_role(advisor, Role.ADVISOR, household_id=household_id)
        require_step_up(advisor, now=now)
        existing = self.store.idempotent_object("treasury.policy", household_id, idempotency_key)
        if existing:
            return self.store.require_policy(existing)
        if any(row.household_id == household_id for row in self.store.policies.values()):
            raise Conflict("initial policy already exists")
        if effective_at <= now + self.minimum_future_delay:
            raise ValidationError("policy effective time must be in the future")
        signers = self._validate_signers(
            household_id=household_id, signer_user_ids=signer_user_ids, threshold=approval_threshold
        )
        row = TreasuryPolicyVersion(
            id=new_id(),
            household_id=household_id,
            version=1,
            base_version_id=None,
            effective_at=effective_at,
            terms=self._validate_terms(terms),
            signer_user_ids=signers,
            approval_threshold=approval_threshold,
            state=PolicyState.PENDING_APPROVAL,
            created_by=advisor.user_id,
            created_at=now,
            idempotency_key=idempotency_key,
        )
        self.store.policies[row.id] = row
        self.store.remember_idempotency("treasury.policy", household_id, idempotency_key, row.id)
        self.store.audit(
            at=now,
            actor_id=advisor.user_id,
            action="treasury.policy.initial.proposed",
            object_id=row.id,
            detail={"household_id": household_id, "version": 1},
        )
        return row

    def propose_policy_amendment(
        self,
        *,
        advisor: ActorContext,
        household_id: str,
        base_version_id: str,
        effective_at: object,
        terms: dict[str, Any],
        signer_user_ids: Iterable[str],
        approval_threshold: int,
        idempotency_key: str,
    ) -> TreasuryPolicyVersion:
        now = self.clock.now()
        require_role(advisor, Role.ADVISOR, household_id=household_id)
        require_step_up(advisor, now=now)
        existing = self.store.idempotent_object("treasury.policy", household_id, idempotency_key)
        if existing:
            return self.store.require_policy(existing)
        base = self.store.require_policy(base_version_id)
        if base.household_id != household_id or base.state is not PolicyState.APPROVED:
            raise Conflict("base policy must be an approved policy in the household")
        latest = max(
            (row for row in self.store.policies.values() if row.household_id == household_id),
            key=lambda row: row.version,
        )
        if latest.id != base.id:
            raise Conflict("base policy is stale")
        if any(
            row.household_id == household_id
            and row.base_version_id == base.id
            and row.state is PolicyState.PENDING_APPROVAL
            for row in self.store.policies.values()
        ):
            raise Conflict("another amendment is already pending from this base version")
        if effective_at <= now + self.minimum_future_delay or effective_at <= base.effective_at:
            raise ValidationError("amendment must be future-effective after the base policy")
        signers = self._validate_signers(
            household_id=household_id, signer_user_ids=signer_user_ids, threshold=approval_threshold
        )
        row = TreasuryPolicyVersion(
            id=new_id(),
            household_id=household_id,
            version=base.version + 1,
            base_version_id=base.id,
            effective_at=effective_at,
            terms=self._validate_terms(terms),
            signer_user_ids=signers,
            approval_threshold=approval_threshold,
            state=PolicyState.PENDING_APPROVAL,
            created_by=advisor.user_id,
            created_at=now,
            idempotency_key=idempotency_key,
        )
        self.store.policies[row.id] = row
        self.store.remember_idempotency("treasury.policy", household_id, idempotency_key, row.id)
        self.store.audit(
            at=now,
            actor_id=advisor.user_id,
            action="treasury.policy.amendment.proposed",
            object_id=row.id,
            detail={"household_id": household_id, "version": row.version, "base": base.id},
        )
        return row

    def approve_policy(self, *, actor: ActorContext, policy_id: str, expected_revision: int) -> TreasuryPolicyVersion:
        now = self.clock.now()
        policy = self.store.require_policy(policy_id)
        require_household(actor, policy.household_id)
        require_step_up(actor, now=now)
        if policy.state is not PolicyState.PENDING_APPROVAL:
            if policy.state is PolicyState.APPROVED:
                return policy
            raise Conflict("policy is not pending approval")
        if policy.revision != expected_revision:
            raise Conflict("policy revision conflict")
        if actor.user_id not in policy.signer_user_ids:
            raise Forbidden("actor is not a designated policy signer")
        if any(a.workflow_type == "treasury_policy" and a.workflow_id == policy.id and a.signer_user_id == actor.user_id for a in self.store.approvals):
            return policy
        approval = Approval(
            id=new_id(),
            workflow_type="treasury_policy",
            workflow_id=policy.id,
            signer_user_id=actor.user_id,
            approved_at=now,
            workflow_revision=policy.revision,
        )
        self.store.approvals.append(approval)
        approvals = self.store.approvals_for("treasury_policy", policy.id)
        advisor_approved = any(
            any(
                membership.user_id == item.signer_user_id
                and membership.household_id == policy.household_id
                and membership.role is Role.ADVISOR
                and membership.revoked_at is None
                for membership in self.store.memberships.values()
            )
            for item in approvals
        )
        if len({item.signer_user_id for item in approvals}) >= policy.approval_threshold and advisor_approved:
            if policy.base_version_id is not None:
                latest_approved = max(
                    (
                        row
                        for row in self.store.policies.values()
                        if row.household_id == policy.household_id and row.state is PolicyState.APPROVED
                    ),
                    key=lambda row: row.version,
                    default=None,
                )
                if latest_approved is None or latest_approved.id != policy.base_version_id:
                    raise Conflict("policy base changed before final approval")
            policy.state = PolicyState.APPROVED
            policy.approved_at = now
            policy.revision += 1
            self._queue_policy_side_effects(policy)
        return policy

    def active_policy(self, *, household_id: str, at: object | None = None) -> TreasuryPolicyVersion:
        moment = at or self.clock.now()
        candidates = [
            row
            for row in self.store.policies.values()
            if row.household_id == household_id
            and row.state in {PolicyState.APPROVED, PolicyState.SUPERSEDED}
            and row.effective_at <= moment
        ]
        if not candidates:
            raise Conflict("no effective approved treasury policy")
        return max(candidates, key=lambda row: (row.effective_at, row.version))

    def activate_due_policies(self) -> list[str]:
        now = self.clock.now()
        changed: list[str] = []
        households = {row.household_id for row in self.store.policies.values()}
        for household_id in households:
            effective = [
                row
                for row in self.store.policies.values()
                if row.household_id == household_id
                and row.state in {PolicyState.APPROVED, PolicyState.SUPERSEDED}
                and row.effective_at <= now
            ]
            if not effective:
                continue
            newest = max(effective, key=lambda row: (row.effective_at, row.version))
            for row in effective:
                target = PolicyState.APPROVED if row.id == newest.id else PolicyState.SUPERSEDED
                if row.state is not target:
                    row.state = target
                    changed.append(row.id)
        return changed

    def request_cash_operation(
        self,
        *,
        actor: ActorContext,
        household_id: str,
        entity_id: str | None,
        policy_version_id: str,
        operation_type: str,
        amount_minor: int,
        currency: str,
        requested_effective_at: object,
        rationale: str,
        conflict_key: str,
        idempotency_key: str,
    ) -> CashOperation:
        now = self.clock.now()
        require_entity(actor, household_id, entity_id)
        existing = self.store.idempotent_object("treasury.cash_operation", household_id, idempotency_key)
        if existing:
            return self.store.require_cash_operation(existing)
        policy = self.store.require_policy(policy_version_id)
        if policy.household_id != household_id or policy.state is not PolicyState.APPROVED:
            raise Conflict("cash operation requires an approved household policy")
        if requested_effective_at < max(now, policy.effective_at):
            raise ValidationError("cash operation cannot predate the governing policy or current time")
        terms = policy.terms
        if operation_type not in self.ALLOWED_OPERATION_TYPES or operation_type not in terms["permitted_operation_types"]:
            raise ValidationError("operation type is not permitted by policy")
        if amount_minor <= 0 or amount_minor > int(terms["cash_operation_limit_minor"]):
            raise ValidationError("cash operation amount is outside policy")
        if currency.upper() != terms["currency"]:
            raise ValidationError("cash operation currency conflicts with policy")
        if not rationale.strip() or len(rationale.strip()) > 2_000:
            raise ValidationError("rationale is required")
        if not conflict_key.strip() or len(conflict_key) > 160:
            raise ValidationError("conflict key is required")
        if any(
            row.household_id == household_id
            and row.conflict_key == conflict_key
            and row.state in {CashOperationState.PENDING_APPROVAL, CashOperationState.APPROVED_FOR_INTAKE}
            for row in self.store.cash_operations.values()
        ):
            raise Conflict("conflicting cash operation already exists")
        row = CashOperation(
            id=new_id(),
            household_id=household_id,
            entity_id=entity_id,
            policy_version_id=policy.id,
            operation_type=operation_type,
            amount_minor=amount_minor,
            currency=currency.upper(),
            requested_effective_at=requested_effective_at,
            rationale=rationale.strip(),
            conflict_key=conflict_key,
            signer_user_ids=policy.signer_user_ids,
            approval_threshold=policy.approval_threshold,
            state=CashOperationState.PENDING_APPROVAL,
            created_by=actor.user_id,
            created_at=now,
            idempotency_key=idempotency_key,
        )
        self.store.cash_operations[row.id] = row
        self.store.remember_idempotency("treasury.cash_operation", household_id, idempotency_key, row.id)
        self.store.audit(
            at=now,
            actor_id=actor.user_id,
            action="treasury.cash_operation.requested",
            object_id=row.id,
            detail={"household_id": household_id, "execution_state": "not_executable"},
        )
        return row

    def approve_cash_operation(
        self, *, actor: ActorContext, operation_id: str, expected_revision: int
    ) -> CashOperation:
        now = self.clock.now()
        operation = self.store.require_cash_operation(operation_id)
        require_household(actor, operation.household_id)
        require_step_up(actor, now=now)
        if operation.state is not CashOperationState.PENDING_APPROVAL:
            if operation.state is CashOperationState.APPROVED_FOR_INTAKE:
                return operation
            raise Conflict("cash operation is not pending approval")
        if operation.revision != expected_revision:
            raise Conflict("cash operation revision conflict")
        if actor.user_id not in operation.signer_user_ids:
            raise Forbidden("actor is not a designated cash-operation signer")
        if any(a.workflow_type == "cash_operation" and a.workflow_id == operation.id and a.signer_user_id == actor.user_id for a in self.store.approvals):
            return operation
        policy = self.store.require_policy(operation.policy_version_id)
        if policy.state not in {PolicyState.APPROVED, PolicyState.SUPERSEDED}:
            raise Conflict("governing policy is no longer valid")
        self.store.approvals.append(
            Approval(
                id=new_id(),
                workflow_type="cash_operation",
                workflow_id=operation.id,
                signer_user_id=actor.user_id,
                approved_at=now,
                workflow_revision=operation.revision,
            )
        )
        approvals = self.store.approvals_for("cash_operation", operation.id)
        advisor_approved = any(
            any(
                membership.user_id == item.signer_user_id
                and membership.household_id == operation.household_id
                and membership.role is Role.ADVISOR
                and membership.revoked_at is None
                for membership in self.store.memberships.values()
            )
            for item in approvals
        )
        if len({item.signer_user_id for item in approvals}) >= operation.approval_threshold and advisor_approved:
            operation.state = CashOperationState.APPROVED_FOR_INTAKE
            operation.approved_at = now
            operation.revision += 1
            self._queue_cash_side_effects(operation)
        return operation

    def cancel_cash_operation(self, *, actor: ActorContext, operation_id: str, expected_revision: int) -> CashOperation:
        now = self.clock.now()
        operation = self.store.require_cash_operation(operation_id)
        require_household(actor, operation.household_id)
        if actor.user_id != operation.created_by and actor.role is not Role.ADVISOR:
            raise Forbidden("only the requester or advisor may cancel")
        if operation.revision != expected_revision or operation.state is not CashOperationState.PENDING_APPROVAL:
            raise Conflict("cash operation cannot be cancelled")
        operation.state = CashOperationState.CANCELLED
        operation.revision += 1
        self.store.audit(
            at=now,
            actor_id=actor.user_id,
            action="treasury.cash_operation.cancelled",
            object_id=operation.id,
            detail={},
        )
        return operation

    def _queue_policy_side_effects(self, policy: TreasuryPolicyVersion) -> None:
        now = self.clock.now()
        self.store.outbox.extend(
            [
                OutboxMessage(
                    id=new_id(),
                    channel="mas_intake",
                    topic="mas.treasury_policy.approved",
                    aggregate_id=policy.id,
                    payload={
                        "direction": "outbound_only",
                        "workflow_kind": "treasury_policy_amendment",
                        "policy_version_id": policy.id,
                        "household_id": policy.household_id,
                        "effective_at": policy.effective_at.isoformat(),
                        "execution": "none",
                    },
                    created_at=now,
                    available_at=now,
                ),
                OutboxMessage(
                    id=new_id(),
                    channel="telegram",
                    topic="treasury.policy.approved",
                    aggregate_id=policy.id,
                    payload={
                        "template": "treasury_policy_approved",
                        "policy_version_id": policy.id,
                        "household_id": policy.household_id,
                        "contains_client_documents": False,
                    },
                    created_at=now,
                    available_at=now,
                ),
            ]
        )
        self.store.recalculations.append(
            RecalculationJob(
                id=new_id(),
                household_id=policy.household_id,
                reason="treasury_policy_version_approved",
                source_id=policy.id,
                requested_at=now,
            )
        )

    def _queue_cash_side_effects(self, operation: CashOperation) -> None:
        now = self.clock.now()
        self.store.outbox.extend(
            [
                OutboxMessage(
                    id=new_id(),
                    channel="mas_intake",
                    topic="mas.cash_operation.approved_for_intake",
                    aggregate_id=operation.id,
                    payload={
                        "direction": "outbound_only",
                        "workflow_kind": "cash_operation",
                        "cash_operation_id": operation.id,
                        "household_id": operation.household_id,
                        "entity_id": operation.entity_id,
                        "execution": "none",
                        "trade": "none",
                        "money_movement": "none",
                    },
                    created_at=now,
                    available_at=now,
                ),
                OutboxMessage(
                    id=new_id(),
                    channel="telegram",
                    topic="treasury.cash_operation.approved",
                    aggregate_id=operation.id,
                    payload={
                        "template": "cash_operation_approved_for_intake",
                        "cash_operation_id": operation.id,
                        "household_id": operation.household_id,
                        "contains_bank_coordinates": False,
                    },
                    created_at=now,
                    available_at=now,
                ),
            ]
        )
        self.store.recalculations.append(
            RecalculationJob(
                id=new_id(),
                household_id=operation.household_id,
                reason="cash_operation_approved_for_intake",
                source_id=operation.id,
                requested_at=now,
            )
        )
