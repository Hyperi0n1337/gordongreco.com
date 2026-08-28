from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Iterable

from .clock import Clock
from .errors import Conflict, Expired, Forbidden, Unauthorized, ValidationError
from .ids import new_id, random_recovery_code, random_token
from .memory import MemoryStore
from .models import (
    ActorContext,
    Invitation,
    MagicLink,
    Membership,
    OutboxMessage,
    RecoveryCode,
    Role,
    Session,
    User,
)
from .scope import derive_actor_context, require_household, require_role, require_step_up
from .security import (
    SecretVault,
    TokenHasher,
    generate_totp_secret,
    new_session_token,
    normalize_email,
    provisioning_uri,
    verify_totp,
)


@dataclass(frozen=True)
class AuthConfig:
    invitation_ttl: timedelta = timedelta(days=7)
    magic_link_ttl: timedelta = timedelta(minutes=10)
    session_ttl: timedelta = timedelta(hours=12)
    step_up_ttl: timedelta = timedelta(minutes=15)
    recovery_code_count: int = 10


@dataclass(frozen=True)
class IssuedSecret:
    id: str
    secret: str
    expires_at: object


class AuthService:
    def __init__(
        self,
        *,
        store: MemoryStore,
        clock: Clock,
        invitation_hasher: TokenHasher,
        session_hasher: TokenHasher,
        recovery_hasher: TokenHasher,
        vault: SecretVault,
        config: AuthConfig | None = None,
    ) -> None:
        self.store = store
        self.clock = clock
        self.invitation_hasher = invitation_hasher
        self.session_hasher = session_hasher
        self.recovery_hasher = recovery_hasher
        self.vault = vault
        self.config = config or AuthConfig()

    def _session_by_token(self, token: str) -> Session:
        digest = self.session_hasher.digest(token)
        for session in self.store.sessions.values():
            if session.token_digest == digest:
                return session
        raise Unauthorized("invalid session")

    def authenticate(self, token: str) -> ActorContext:
        now = self.clock.now()
        session = self._session_by_token(token)
        session.last_seen_at = now
        return derive_actor_context(self.store, session, now=now)

    def invite_user(
        self,
        *,
        advisor: ActorContext,
        email: str,
        display_name: str,
        household_id: str,
        role: Role = Role.CLIENT,
        entity_ids: Iterable[str] = (),
    ) -> IssuedSecret:
        now = self.clock.now()
        require_role(advisor, Role.ADVISOR, household_id=household_id)
        require_step_up(advisor, now=now)
        if role not in {Role.CLIENT, Role.ADVISOR, Role.OPERATIONS}:
            raise ValidationError("role cannot be invited")
        normalized = normalize_email(email)
        if not display_name.strip() or len(display_name.strip()) > 120:
            raise ValidationError("display name is required")
        user = self.store.find_user_by_email(normalized)
        if user is None:
            user = User(id=new_id(), email=normalized, display_name=display_name.strip())
            self.store.add_user(user)
        elif user.revoked_at is not None:
            raise Conflict("revoked account requires explicit recovery review")

        existing = next(
            (
                m
                for m in self.store.memberships.values()
                if m.user_id == user.id and m.household_id == household_id and m.revoked_at is None
            ),
            None,
        )
        membership = existing or Membership(
            id=new_id(),
            user_id=user.id,
            household_id=household_id,
            role=role,
            entity_ids=frozenset(entity_ids),
        )
        membership.role = role
        membership.entity_ids = frozenset(entity_ids)
        self.store.memberships[membership.id] = membership

        for invitation in self.store.invitations.values():
            if invitation.user_id == user.id and invitation.consumed_at is None:
                invitation.revoked_at = now
        token = random_token(32)
        invitation = Invitation(
            id=new_id(),
            user_id=user.id,
            token_digest=self.invitation_hasher.digest(token),
            expires_at=now + self.config.invitation_ttl,
            created_by=advisor.user_id,
            created_at=now,
        )
        self.store.invitations[invitation.id] = invitation
        self.store.outbox.append(
            OutboxMessage(
                id=new_id(),
                channel="email",
                topic="portal.invitation",
                aggregate_id=invitation.id,
                payload={
                    "recipient": user.email,
                    "template": "portal_invitation",
                    "invitation_id": invitation.id,
                    "delivery_mode": "outbox_only",
                },
                created_at=now,
                available_at=now,
            )
        )
        self.store.audit(
            at=now,
            actor_id=advisor.user_id,
            action="portal.invitation.created",
            object_id=invitation.id,
            detail={"user_id": user.id, "household_id": household_id, "role": role.value},
        )
        return IssuedSecret(invitation.id, token, invitation.expires_at)

    def request_magic_link(self, email: str) -> IssuedSecret | None:
        """Return None for unknown addresses; the HTTP response remains generic."""

        now = self.clock.now()
        normalized = normalize_email(email)
        user = self.store.find_user_by_email(normalized)
        if user is None or user.revoked_at is not None:
            return None
        memberships = self.store.active_memberships(user.id)
        active_invites = [
            row
            for row in self.store.invitations.values()
            if row.user_id == user.id
            and row.revoked_at is None
            and row.consumed_at is None
            and row.expires_at > now
        ]
        if not memberships or (not user.active and not active_invites):
            return None
        for link in self.store.magic_links.values():
            if link.user_id == user.id and link.consumed_at is None and link.revoked_at is None:
                link.revoked_at = now
        token = random_token(32)
        link = MagicLink(
            id=new_id(),
            user_id=user.id,
            token_digest=self.invitation_hasher.digest(token),
            expires_at=now + self.config.magic_link_ttl,
            created_at=now,
        )
        self.store.magic_links[link.id] = link
        self.store.outbox.append(
            OutboxMessage(
                id=new_id(),
                channel="email",
                topic="portal.magic_link",
                aggregate_id=link.id,
                payload={
                    "recipient": user.email,
                    "template": "passwordless_magic_link",
                    "magic_link_id": link.id,
                    "delivery_mode": "outbox_only",
                },
                created_at=now,
                available_at=now,
            )
        )
        return IssuedSecret(link.id, token, link.expires_at)

    def consume_magic_link(self, token: str) -> IssuedSecret:
        now = self.clock.now()
        digest = self.invitation_hasher.digest(token)
        link = next((row for row in self.store.magic_links.values() if row.token_digest == digest), None)
        if link is None:
            raise Unauthorized("invalid magic link")
        if link.revoked_at is not None or link.consumed_at is not None:
            raise Unauthorized("magic link already used or revoked")
        if link.expires_at <= now:
            raise Expired("magic link expired")
        user = self.store.users.get(link.user_id)
        if user is None or user.revoked_at is not None or not self.store.active_memberships(user.id):
            raise Unauthorized("account is not active")
        if not user.active:
            invitation = next(
                (
                    row
                    for row in self.store.invitations.values()
                    if row.user_id == user.id
                    and row.revoked_at is None
                    and row.consumed_at is None
                    and row.expires_at > now
                ),
                None,
            )
            if invitation is None:
                raise Unauthorized("invitation is not active")
            invitation.consumed_at = now
            user.active = True
        link.consumed_at = now
        raw = new_session_token()
        session = Session(
            id=new_id(),
            user_id=user.id,
            token_digest=self.session_hasher.digest(raw),
            auth_epoch=user.auth_epoch,
            created_at=now,
            expires_at=now + self.config.session_ttl,
            last_seen_at=now,
        )
        self.store.sessions[session.id] = session
        self.store.audit(
            at=now,
            actor_id=user.id,
            action="portal.session.created",
            object_id=session.id,
            detail={"auth_level": 1},
        )
        return IssuedSecret(session.id, raw, session.expires_at)

    def begin_totp_enrollment(self, session_token: str) -> tuple[str, str]:
        now = self.clock.now()
        session = self._session_by_token(session_token)
        actor = derive_actor_context(self.store, session, now=now)
        user = self.store.users[actor.user_id]
        secret = generate_totp_secret()
        context = {"user_id": user.id, "purpose": "portal_totp_v1"}
        user.totp_ciphertext = self.vault.encrypt(secret.encode(), context=context)
        user.totp_confirmed_at = None
        user.totp_last_counter = -1
        return secret, provisioning_uri(secret=secret, email=user.email)

    def confirm_totp_enrollment(self, session_token: str, code: str) -> list[str]:
        now = self.clock.now()
        session = self._session_by_token(session_token)
        actor = derive_actor_context(self.store, session, now=now)
        user = self.store.users[actor.user_id]
        if not user.totp_ciphertext:
            raise Conflict("TOTP enrollment has not started")
        context = {"user_id": user.id, "purpose": "portal_totp_v1"}
        secret = self.vault.decrypt(user.totp_ciphertext, context=context).decode()
        counter = verify_totp(secret, code, now=now, last_counter=user.totp_last_counter)
        user.totp_last_counter = counter
        user.totp_confirmed_at = now
        session.auth_level = 2
        session.step_up_until = now + self.config.step_up_ttl
        return self._rotate_recovery_codes(user.id, now=now)

    def step_up_totp(self, session_token: str, code: str) -> ActorContext:
        now = self.clock.now()
        session = self._session_by_token(session_token)
        actor = derive_actor_context(self.store, session, now=now)
        user = self.store.users[actor.user_id]
        if not user.totp_ciphertext or user.totp_confirmed_at is None:
            raise Forbidden("TOTP is not enrolled")
        context = {"user_id": user.id, "purpose": "portal_totp_v1"}
        secret = self.vault.decrypt(user.totp_ciphertext, context=context).decode()
        counter = verify_totp(secret, code, now=now, last_counter=user.totp_last_counter)
        user.totp_last_counter = counter
        session.auth_level = 2
        session.step_up_until = now + self.config.step_up_ttl
        self.store.audit(
            at=now,
            actor_id=user.id,
            action="portal.session.step_up",
            object_id=session.id,
            detail={"method": "totp"},
        )
        return derive_actor_context(self.store, session, now=now)

    def use_recovery_code(self, session_token: str, recovery_code: str) -> ActorContext:
        now = self.clock.now()
        session = self._session_by_token(session_token)
        actor = derive_actor_context(self.store, session, now=now)
        digest = self.recovery_hasher.digest(recovery_code.strip().upper())
        row = next(
            (
                item
                for item in self.store.recovery_codes.values()
                if item.user_id == actor.user_id
                and item.code_digest == digest
                and item.consumed_at is None
                and item.revoked_at is None
            ),
            None,
        )
        if row is None:
            raise Unauthorized("invalid recovery code")
        row.consumed_at = now
        session.auth_level = 2
        session.step_up_until = now + timedelta(minutes=5)
        self.store.audit(
            at=now,
            actor_id=actor.user_id,
            action="portal.session.recovered",
            object_id=session.id,
            detail={"method": "one_time_recovery_code", "recovery_code_id": row.id},
        )
        return derive_actor_context(self.store, session, now=now)

    def reset_totp_after_recovery(self, session_token: str) -> tuple[str, str]:
        now = self.clock.now()
        session = self._session_by_token(session_token)
        actor = derive_actor_context(self.store, session, now=now)
        require_step_up(actor, now=now)
        user = self.store.users[actor.user_id]
        user.totp_ciphertext = None
        user.totp_confirmed_at = None
        user.totp_last_counter = -1
        for code in self.store.recovery_codes.values():
            if code.user_id == user.id and code.consumed_at is None:
                code.revoked_at = now
        return self.begin_totp_enrollment(session_token)

    def _rotate_recovery_codes(self, user_id: str, *, now: object) -> list[str]:
        for row in self.store.recovery_codes.values():
            if row.user_id == user_id and row.consumed_at is None:
                row.revoked_at = now
        plain: list[str] = []
        for _ in range(self.config.recovery_code_count):
            code = random_recovery_code()
            plain.append(code)
            row = RecoveryCode(
                id=new_id(),
                user_id=user_id,
                code_digest=self.recovery_hasher.digest(code.upper()),
                created_at=now,
            )
            self.store.recovery_codes[row.id] = row
        return plain

    def revoke_membership(
        self,
        *,
        advisor: ActorContext,
        user_id: str,
        household_id: str,
        reason: str,
    ) -> None:
        now = self.clock.now()
        require_role(advisor, Role.ADVISOR, household_id=household_id)
        require_step_up(advisor, now=now)
        target = self.store.users.get(user_id)
        if target is None:
            raise ValidationError("target user not found")
        affected = [
            m
            for m in self.store.memberships.values()
            if m.user_id == user_id and m.household_id == household_id and m.revoked_at is None
        ]
        if not affected:
            raise Conflict("membership is already revoked or absent")
        for membership in affected:
            membership.revoked_at = now
        target.auth_epoch += 1
        for session in self.store.sessions.values():
            if session.user_id == user_id and session.revoked_at is None:
                session.revoked_at = now
        for invite in self.store.invitations.values():
            if invite.user_id == user_id and invite.revoked_at is None and invite.consumed_at is None:
                invite.revoked_at = now
        for link in self.store.magic_links.values():
            if link.user_id == user_id and link.revoked_at is None and link.consumed_at is None:
                link.revoked_at = now
        self.store.audit(
            at=now,
            actor_id=advisor.user_id,
            action="portal.membership.revoked",
            object_id=user_id,
            detail={"household_id": household_id, "reason": reason[:240]},
        )

    def logout(self, session_token: str) -> None:
        session = self._session_by_token(session_token)
        session.revoked_at = self.clock.now()
