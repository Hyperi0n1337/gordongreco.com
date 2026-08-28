from __future__ import annotations

from collections import Counter
from datetime import datetime

from .errors import Forbidden, Unauthorized
from .memory import MemoryStore
from .models import ActorContext, Membership, Role, Session


def derive_actor_context(store: MemoryStore, session: Session, *, now: datetime) -> ActorContext:
    user = store.users.get(session.user_id)
    if user is None or not user.active or user.revoked_at is not None:
        raise Unauthorized("account is inactive")
    if session.revoked_at is not None or session.expires_at <= now:
        raise Unauthorized("session expired")
    if session.auth_epoch != user.auth_epoch:
        raise Unauthorized("session revoked by authorization change")
    memberships = store.active_memberships(user.id)
    if not memberships:
        raise Unauthorized("no active portal membership")
    role_counts = Counter(m.role for m in memberships)
    role = Role.ADVISOR if role_counts[Role.ADVISOR] else Role.OPERATIONS if role_counts[Role.OPERATIONS] else Role.CLIENT
    household_ids = frozenset(m.household_id for m in memberships)
    entity_ids = frozenset(entity for m in memberships for entity in m.entity_ids)
    return ActorContext(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=role,
        household_ids=household_ids,
        entity_ids=entity_ids,
        session_id=session.id,
        auth_level=session.auth_level,
        step_up_until=session.step_up_until,
        entity_scope=frozenset(
            (membership.household_id, entity_id)
            for membership in memberships
            for entity_id in membership.entity_ids
        ),
        role_scope=frozenset((membership.household_id, membership.role) for membership in memberships),
    )


def require_household(actor: ActorContext, household_id: str) -> None:
    if household_id not in actor.household_ids:
        raise Forbidden("household is outside server-derived scope")


def require_entity(actor: ActorContext, household_id: str, entity_id: str | None) -> None:
    require_household(actor, household_id)
    if entity_id is not None and (household_id, entity_id) not in actor.entity_scope:
        raise Forbidden("entity is outside server-derived household/entity scope")


def require_role(
    actor: ActorContext, *roles: Role, household_id: str | None = None
) -> None:
    if household_id is None:
        if actor.role not in roles:
            raise Forbidden("role is not authorized")
        return
    require_household(actor, household_id)
    if not any((household_id, role) in actor.role_scope for role in roles):
        raise Forbidden("role is not authorized for this household")


def require_step_up(actor: ActorContext, *, now: datetime) -> None:
    if not actor.has_step_up(now):
        raise Forbidden("TOTP step-up required")
