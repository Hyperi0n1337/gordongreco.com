from datetime import timedelta

import pytest

from conftest import ENTITY_SHARED, HH_A, HH_B
from portal_core.errors import Conflict, Forbidden, ValidationError
from portal_core.models import CashOperationState, PolicyState
from portal_core.treasury import TreasuryService


TERMS = {
    "currency": "USD",
    "minimum_operating_reserve_minor": 2_500_000,
    "cash_operation_limit_minor": 1_000_000,
    "permitted_operation_types": ["operating_reserve_adjustment", "planned_tax_payment_reserve"],
    "notes": "fictional test policy",
}


def policy(service, actor_factory, clock):
    row = service.propose_initial_policy(
        advisor=actor_factory("advisor-a"), household_id=HH_A,
        effective_at=clock.now() + timedelta(minutes=10), terms=TERMS,
        signer_user_ids=("advisor-a", "client-a"), approval_threshold=2,
        idempotency_key="initial-policy-test-001",
    )
    service.approve_policy(actor=actor_factory("client-a"), policy_id=row.id, expected_revision=1)
    assert row.state is PolicyState.PENDING_APPROVAL
    service.approve_policy(actor=actor_factory("advisor-a"), policy_id=row.id, expected_revision=1)
    assert row.state is PolicyState.APPROVED and row.revision == 2
    return row


def test_policy_requires_designated_advisor_step_up_and_future_effective(store, clock, actor_factory):
    service = TreasuryService(store=store, clock=clock)
    with pytest.raises(Forbidden):
        service.propose_initial_policy(
            advisor=actor_factory("advisor-a", False), household_id=HH_A,
            effective_at=clock.now() + timedelta(minutes=10), terms=TERMS,
            signer_user_ids=("advisor-a",), approval_threshold=1, idempotency_key="policy-no-stepup-001")
    with pytest.raises(ValidationError):
        service.propose_initial_policy(
            advisor=actor_factory("advisor-a"), household_id=HH_A,
            effective_at=clock.now() + timedelta(minutes=1), terms=TERMS,
            signer_user_ids=("advisor-a",), approval_threshold=1, idempotency_key="policy-too-soon-001")
    with pytest.raises(ValidationError):
        service.propose_initial_policy(
            advisor=actor_factory("advisor-a"), household_id=HH_A,
            effective_at=clock.now() + timedelta(minutes=10), terms=TERMS,
            signer_user_ids=("client-a",), approval_threshold=1, idempotency_key="policy-no-advisor-001")


def test_policy_approval_queues_outbound_only_mas_telegram_and_recalculation(store, clock, actor_factory):
    service = TreasuryService(store=store, clock=clock)
    row = policy(service, actor_factory, clock)
    topics = {m.topic for m in store.outbox}
    assert {"mas.treasury_policy.approved", "treasury.policy.approved"} <= topics
    mas = next(m for m in store.outbox if m.topic == "mas.treasury_policy.approved")
    assert mas.payload["direction"] == "outbound_only" and mas.payload["execution"] == "none"
    assert store.recalculations[0].source_id == row.id
    with pytest.raises(Conflict):
        service.active_policy(household_id=HH_A)
    clock.advance(minutes=10)
    assert service.active_policy(household_id=HH_A).id == row.id


def test_amendment_conflicts_idempotency_future_version_and_activation(store, clock, actor_factory):
    service = TreasuryService(store=store, clock=clock)
    base = policy(service, actor_factory, clock)
    amendment = service.propose_policy_amendment(
        advisor=actor_factory("advisor-a"), household_id=HH_A, base_version_id=base.id,
        effective_at=clock.now() + timedelta(minutes=20), terms=TERMS | {"cash_operation_limit_minor": 900_000},
        signer_user_ids=("advisor-a", "client-a"), approval_threshold=2,
        idempotency_key="amendment-policy-test-001")
    same = service.propose_policy_amendment(
        advisor=actor_factory("advisor-a"), household_id=HH_A, base_version_id=base.id,
        effective_at=clock.now() + timedelta(minutes=20), terms=TERMS,
        signer_user_ids=("advisor-a", "client-a"), approval_threshold=2,
        idempotency_key="amendment-policy-test-001")
    assert same.id == amendment.id
    with pytest.raises(Conflict):
        service.propose_policy_amendment(
            advisor=actor_factory("advisor-a"), household_id=HH_A, base_version_id=base.id,
            effective_at=clock.now() + timedelta(minutes=30), terms=TERMS,
            signer_user_ids=("advisor-a",), approval_threshold=1,
            idempotency_key="second-pending-amendment-test")
    service.approve_policy(actor=actor_factory("client-a"), policy_id=amendment.id, expected_revision=1)
    service.approve_policy(actor=actor_factory("advisor-a"), policy_id=amendment.id, expected_revision=1)
    clock.advance(minutes=20)
    changed = service.activate_due_policies()
    assert base.state is PolicyState.SUPERSEDED and amendment.state is PolicyState.APPROVED
    assert base.id in changed


def test_cash_operation_is_approval_for_intake_never_execution(store, clock, actor_factory):
    service = TreasuryService(store=store, clock=clock)
    governing = policy(service, actor_factory, clock)
    operation = service.request_cash_operation(
        actor=actor_factory("client-a"), household_id=HH_A, entity_id=ENTITY_SHARED,
        policy_version_id=governing.id, operation_type="operating_reserve_adjustment",
        amount_minor=500_000, currency="usd", requested_effective_at=governing.effective_at,
        rationale="fictional reserve adjustment", conflict_key="reserve-2026-09.test",
        idempotency_key="cash-operation-test-001")
    assert operation.execution_state == "not_executable"
    service.approve_cash_operation(actor=actor_factory("client-a"), operation_id=operation.id, expected_revision=1)
    assert operation.state is CashOperationState.PENDING_APPROVAL
    service.approve_cash_operation(actor=actor_factory("advisor-a"), operation_id=operation.id, expected_revision=1)
    assert operation.state is CashOperationState.APPROVED_FOR_INTAKE
    mas = next(m for m in store.outbox if m.topic == "mas.cash_operation.approved_for_intake")
    assert mas.payload["trade"] == mas.payload["money_movement"] == mas.payload["execution"] == "none"
    assert any(m.channel == "telegram" and m.aggregate_id == operation.id for m in store.outbox)
    assert any(job.source_id == operation.id for job in store.recalculations)


def test_cash_conflict_currency_limit_scope_and_revision_are_enforced(store, clock, actor_factory):
    service = TreasuryService(store=store, clock=clock)
    governing = policy(service, actor_factory, clock)
    kwargs = dict(
        actor=actor_factory("client-a"), household_id=HH_A, entity_id=ENTITY_SHARED,
        policy_version_id=governing.id, operation_type="planned_tax_payment_reserve",
        amount_minor=500_000, currency="USD", requested_effective_at=governing.effective_at,
        rationale="fictional tax reserve", conflict_key="tax-q3.test", idempotency_key="cash-test-002")
    operation = service.request_cash_operation(**kwargs)
    with pytest.raises(Conflict):
        service.request_cash_operation(**(kwargs | {"idempotency_key":"cash-test-003"}))
    with pytest.raises(Conflict):
        service.approve_cash_operation(actor=actor_factory("advisor-a"), operation_id=operation.id, expected_revision=99)
    with pytest.raises(Forbidden):
        service.approve_cash_operation(actor=actor_factory("advisor-b"), operation_id=operation.id, expected_revision=1)
    with pytest.raises(ValidationError):
        service.request_cash_operation(**(kwargs | {"conflict_key":"other.test", "idempotency_key":"cash-test-004", "currency":"EUR"}))
    with pytest.raises(Forbidden):
        service.request_cash_operation(**(kwargs | {"actor":actor_factory("client-b"), "household_id":HH_A, "idempotency_key":"cash-test-005"}))
