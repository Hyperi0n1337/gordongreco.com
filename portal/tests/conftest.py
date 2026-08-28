from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta

import pytest

from portal_core.auth import AuthService
from portal_core.capabilities import CapabilitySigner
from portal_core.clock import FrozenClock
from portal_core.memory import MemoryObjectStore, MemoryStore
from portal_core.models import Membership, Role, Session, User
from portal_core.scope import derive_actor_context
from portal_core.security import TokenHasher
from portal_core.uploads import UploadPolicy, UploadService

HH_A = "household-alpha.test"
HH_B = "household-beta.test"
ENTITY_SHARED = "entity-shared.test"
ENTITY_A = "entity-alpha.test"
ENTITY_B = "entity-beta.test"
NOW = datetime(2026, 8, 28, 17, 26, tzinfo=UTC)


class TestVault:
    """Context-bound reversible test vault; production adapters use KMS envelope encryption."""

    def encrypt(self, plaintext: bytes, *, context: dict[str, str]) -> str:
        body = json.dumps({"context": context, "data": base64.b64encode(plaintext).decode()}, sort_keys=True)
        return base64.urlsafe_b64encode(body.encode()).decode()

    def decrypt(self, ciphertext: str, *, context: dict[str, str]) -> bytes:
        body = json.loads(base64.urlsafe_b64decode(ciphertext.encode()))
        if body["context"] != context:
            raise ValueError("vault encryption context mismatch")
        return base64.b64decode(body["data"])


@pytest.fixture
def clock() -> FrozenClock:
    return FrozenClock(NOW)


@pytest.fixture
def store() -> MemoryStore:
    value = MemoryStore()
    users = [
        User("advisor-a", "advisor.a@example.test", "Advisor A", active=True),
        User("advisor-b", "advisor.b@example.test", "Advisor B", active=True),
        User("client-a", "client.a@example.test", "Client A", active=True),
        User("client-a2", "client.a2@example.test", "Client A2", active=True),
        User("client-b", "client.b@example.test", "Client B", active=True),
        User("operations-a", "operations.a@example.test", "Operations A", active=True),
        User("mixed-user", "mixed@example.test", "Mixed Role", active=True),
    ]
    for user in users:
        value.add_user(user)
    memberships = [
        Membership("m-advisor-a", "advisor-a", HH_A, Role.ADVISOR, frozenset({ENTITY_SHARED, ENTITY_A})),
        Membership("m-advisor-b", "advisor-b", HH_B, Role.ADVISOR, frozenset({ENTITY_SHARED, ENTITY_B})),
        Membership("m-client-a", "client-a", HH_A, Role.CLIENT, frozenset({ENTITY_SHARED, ENTITY_A})),
        Membership("m-client-a2", "client-a2", HH_A, Role.CLIENT, frozenset({ENTITY_SHARED})),
        Membership("m-client-b", "client-b", HH_B, Role.CLIENT, frozenset({ENTITY_SHARED, ENTITY_B})),
        Membership("m-operations-a", "operations-a", HH_A, Role.OPERATIONS, frozenset({ENTITY_SHARED, ENTITY_A})),
        Membership("m-mixed-a", "mixed-user", HH_A, Role.ADVISOR, frozenset({ENTITY_SHARED})),
        Membership("m-mixed-b", "mixed-user", HH_B, Role.CLIENT, frozenset({ENTITY_SHARED})),
    ]
    for row in memberships:
        value.memberships[row.id] = row
    return value


def actor_for(store: MemoryStore, clock: FrozenClock, user_id: str, *, stepped_up: bool = True):
    session = Session(
        id=f"session-{user_id}",
        user_id=user_id,
        token_digest=f"digest-{user_id}",
        auth_epoch=store.users[user_id].auth_epoch,
        created_at=clock.now(),
        expires_at=clock.now() + timedelta(hours=12),
        auth_level=2 if stepped_up else 1,
        step_up_until=clock.now() + timedelta(minutes=15) if stepped_up else None,
    )
    store.sessions[session.id] = session
    return derive_actor_context(store, session, now=clock.now())


@pytest.fixture
def actor_factory(store, clock):
    return lambda user_id, stepped_up=True: actor_for(store, clock, user_id, stepped_up=stepped_up)


@pytest.fixture
def auth_service(store, clock):
    return AuthService(
        store=store,
        clock=clock,
        invitation_hasher=TokenHasher(b"i" * 32),
        session_hasher=TokenHasher(b"s" * 32),
        recovery_hasher=TokenHasher(b"r" * 32),
        vault=TestVault(),
    )


@pytest.fixture
def objects():
    return MemoryObjectStore()


@pytest.fixture
def upload_service(store, objects, clock):
    return UploadService(
        store=store,
        objects=objects,
        capabilities=CapabilitySigner(b"c" * 32),
        clock=clock,
        policy=UploadPolicy(max_document_bytes=1024 * 1024, max_part_bytes=256 * 1024),
    )
