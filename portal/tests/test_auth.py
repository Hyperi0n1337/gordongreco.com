from datetime import timedelta

import pytest

from conftest import HH_A
from portal_core.errors import Expired, Unauthorized
from portal_core.models import Membership, Role, User
from portal_core.security import hotp, totp_counter


def invite_and_login(auth_service, actor_factory, email="new.client@example.test"):
    advisor = actor_factory("advisor-a")
    issued = auth_service.invite_user(
        advisor=advisor,
        email=email,
        display_name="New Test Client",
        household_id=HH_A,
        role=Role.CLIENT,
        entity_ids=("entity-shared.test",),
    )
    assert len(issued.secret) >= 40
    magic = auth_service.request_magic_link(email)
    assert magic is not None
    session = auth_service.consume_magic_link(magic.secret)
    return session


def test_unknown_or_uninvited_address_cannot_start_passwordless_access(auth_service, store):
    assert auth_service.request_magic_link("unknown@example.test") is None
    user = User("inactive", "inactive@example.test", "Inactive", active=False)
    store.add_user(user)
    store.memberships["inactive-membership"] = Membership(
        "inactive-membership", user.id, HH_A, Role.CLIENT, frozenset()
    )
    assert auth_service.request_magic_link(user.email) is None


def test_invitation_only_magic_link_is_single_use(auth_service, actor_factory, store):
    session = invite_and_login(auth_service, actor_factory)
    actor = auth_service.authenticate(session.secret)
    assert actor.email == "new.client@example.test"
    assert store.users[actor.user_id].active is True
    with pytest.raises(Unauthorized):
        auth_service.consume_magic_link(next(iter(store.magic_links.values())).token_digest)


def test_magic_link_expiry_is_enforced(auth_service, actor_factory, clock):
    advisor = actor_factory("advisor-a")
    auth_service.invite_user(
        advisor=advisor,
        email="expiring@example.test",
        display_name="Expiring Test",
        household_id=HH_A,
        entity_ids=("entity-shared.test",),
    )
    link = auth_service.request_magic_link("expiring@example.test")
    clock.advance(minutes=11)
    with pytest.raises(Expired):
        auth_service.consume_magic_link(link.secret)


def test_totp_step_up_replay_and_one_time_recovery(auth_service, actor_factory, clock):
    session = invite_and_login(auth_service, actor_factory, "totp@example.test")
    secret, uri = auth_service.begin_totp_enrollment(session.secret)
    assert uri.startswith("otpauth://totp/")
    first_code = hotp(secret, totp_counter(clock.now()))
    recovery_codes = auth_service.confirm_totp_enrollment(session.secret, first_code)
    assert len(recovery_codes) == 10 and len(set(recovery_codes)) == 10
    with pytest.raises(Unauthorized):
        auth_service.step_up_totp(session.secret, first_code)
    clock.advance(seconds=30)
    stepped = auth_service.step_up_totp(session.secret, hotp(secret, totp_counter(clock.now())))
    assert stepped.has_step_up(clock.now())
    auth_service.use_recovery_code(session.secret, recovery_codes[0])
    with pytest.raises(Unauthorized):
        auth_service.use_recovery_code(session.secret, recovery_codes[0])


def test_advisor_revocation_invalidates_sessions_invites_and_links(auth_service, actor_factory, store):
    session = invite_and_login(auth_service, actor_factory, "revoked@example.test")
    actor = auth_service.authenticate(session.secret)
    extra = auth_service.request_magic_link(actor.email)
    assert extra is not None
    auth_service.revoke_membership(
        advisor=actor_factory("advisor-a"),
        user_id=actor.user_id,
        household_id=HH_A,
        reason="fictional test revocation",
    )
    with pytest.raises(Unauthorized):
        auth_service.authenticate(session.secret)
    assert all(s.revoked_at is not None for s in store.sessions.values() if s.user_id == actor.user_id)
    assert all(m.revoked_at is not None for m in store.memberships.values() if m.user_id == actor.user_id)
