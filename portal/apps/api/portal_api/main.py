from __future__ import annotations

import hashlib
import logging
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import Any, Iterator

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from portal_adapters.kms import AwsKmsVault
from portal_adapters.local_vault import LocalAesGcmVault
from portal_adapters.postgres import DatabaseActor, PortalDatabase
from portal_adapters.s3 import S3PrivateObjectStore
from portal_core.capabilities import CapabilitySigner
from portal_core.ids import new_id, random_recovery_code, random_token
from portal_core.security import (
    TokenHasher,
    generate_totp_secret,
    normalize_email,
    provisioning_uri,
    verify_totp,
)

from .config import Settings
from .http_security import (
    SecurityHeadersMiddleware,
    clear_session_cookies,
    require_csrf,
    require_origin,
    set_session_cookies,
)
from .schemas import (
    ApprovalInput,
    CashOperationInput,
    DeleteInput,
    DocumentRequestInput,
    InviteInput,
    MagicLinkConsume,
    MagicLinkRequest,
    PolicyInput,
    RecoveryCodeInput,
    ReviewInput,
    RevokeInput,
    SupportInput,
    TotpCode,
    UploadBeginInput,
    UploadCompleteInput,
)

log = logging.getLogger("portal_api")


class Services:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.db = PortalDatabase(settings.database_url)
        self.session_hasher = TokenHasher(settings.session_hmac_key, b"portal-session-v1")
        self.invitation_hasher = TokenHasher(settings.invitation_hmac_key, b"portal-link-v1")
        self.recovery_hasher = TokenHasher(settings.invitation_hmac_key, b"portal-recovery-v1")
        self.capabilities = CapabilitySigner(settings.capability_hmac_key)
        if settings.vault_mode == "kms":
            self.vault = AwsKmsVault(key_id=settings.kms_key_id, region_name=settings.aws_region)
        else:
            self.vault = LocalAesGcmVault(settings.local_vault_key)
        self.s3 = S3PrivateObjectStore(
            region_name=settings.aws_region,
            endpoint_url=settings.s3_endpoint_url,
            kms_key_id=settings.kms_key_id if settings.vault_mode == "kms" else None,
        )


def _now() -> datetime:
    return datetime.now(UTC)


def _problem(status: int, code: str, detail: str = "") -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "detail": detail})


def _serialize(row: Any) -> Any:
    if isinstance(row, dict):
        return {key: _serialize(value) for key, value in row.items()}
    if isinstance(row, (list, tuple)):
        return [_serialize(value) for value in row]
    if isinstance(row, datetime):
        return row.isoformat()
    return row


def create_app() -> FastAPI:
    settings = Settings.from_env()
    services = Services(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        services.db.open()
        app.state.services = services
        yield
        services.db.close()

    app = FastAPI(
        title="Gordon Greco Secure Client Portal API",
        version="0.4.2",
        docs_url=None if settings.environment == "production" else "/_docs",
        redoc_url=None,
        openapi_url=None if settings.environment == "production" else "/_openapi.json",
        lifespan=lifespan,
    )
    app.add_middleware(SecurityHeadersMiddleware)

    @app.exception_handler(PermissionError)
    async def permission_error_handler(_: Request, __: PermissionError) -> JSONResponse:
        return JSONResponse(status_code=401, content={"error": {"code": "unauthorized"}})

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled portal error", exc_info=exc)
        return JSONResponse(status_code=500, content={"error": {"code": "internal_error"}})

    def svc(request: Request) -> Services:
        return request.app.state.services

    def actor_tx(request: Request, services: Services = Depends(svc)) -> Iterator[tuple[Any, DatabaseActor]]:
        raw = request.cookies.get("gg_session", "")
        if not raw:
            raise _problem(401, "session_required")
        require_origin(request, services.settings.allowed_origins)
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            require_csrf(request)
        digest = services.session_hasher.digest(raw)
        try:
            with services.db.actor_transaction(digest) as context:
                yield context
        except PermissionError as exc:
            raise _problem(401, "invalid_session") from exc

    def require_step_up(actor: DatabaseActor) -> None:
        if actor.auth_level < 2 or actor.step_up_until is None or actor.step_up_until <= _now():
            raise _problem(403, "totp_step_up_required")

    def require_role(actor: DatabaseActor, *roles: str) -> None:
        if actor.role not in roles:
            raise _problem(403, "role_denied")

    @app.get("/health/live")
    def health_live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    def health_ready(services: Services = Depends(svc)) -> dict[str, str]:
        try:
            with services.db.pool.connection() as conn:
                conn.execute("SELECT 1").fetchone()
            return {"status": "ready"}
        except Exception as exc:
            raise _problem(503, "database_unavailable") from exc

    @app.post("/v1/auth/magic-link", status_code=202)
    def request_magic_link(
        body: MagicLinkRequest,
        request: Request,
        services: Services = Depends(svc),
    ) -> dict[str, str]:
        require_origin(request, services.settings.allowed_origins)
        email = normalize_email(body.email)
        link_id = new_id()
        token = random_token(32)
        digest = services.invitation_hasher.digest(token)
        expires_at = _now() + timedelta(minutes=10)
        ciphertext = services.vault.encrypt(
            token.encode(), context={"purpose": "magic_link", "token_id": link_id}
        )
        with services.db.pool.connection() as conn, conn.transaction():
            conn.execute(
                "SELECT portal.consume_auth_rate_limit(%s, %s, %s)",
                (f"magic:{hashlib.sha256(email.encode()).hexdigest()}", 5, 900),
            )
            conn.execute(
                "SELECT portal.rpc_request_magic_link(%s,%s,%s,%s,%s)",
                (link_id, email, digest, ciphertext, expires_at),
            ).fetchone()
        return {"status": "accepted"}

    @app.post("/v1/auth/magic-link/consume")
    def consume_magic_link(
        body: MagicLinkConsume,
        request: Request,
        response: Response,
        services: Services = Depends(svc),
    ) -> dict[str, object]:
        require_origin(request, services.settings.allowed_origins)
        link_digest = services.invitation_hasher.digest(body.token)
        session_id = new_id()
        session_token = random_token(32)
        session_digest = services.session_hasher.digest(session_token)
        expires_at = _now() + timedelta(hours=12)
        with services.db.pool.connection() as conn, conn.transaction():
            row = conn.execute(
                "SELECT * FROM portal.rpc_consume_magic_link(%s,%s,%s,%s)",
                (link_digest, session_id, session_digest, expires_at),
            ).fetchone()
            if row is None:
                raise _problem(401, "invalid_or_expired_magic_link")
        csrf = random_token(24)
        set_session_cookies(
            response,
            session_token=session_token,
            csrf_token=csrf,
            secure=services.settings.secure_cookies,
        )
        return {"session_id": session_id, "totp_enrolled": bool(row["totp_enrolled"])}

    @app.post("/v1/auth/invitation/consume")
    def consume_invitation(
        body: MagicLinkConsume,
        request: Request,
        response: Response,
        services: Services = Depends(svc),
    ) -> dict[str, object]:
        require_origin(request, services.settings.allowed_origins)
        invitation_digest = services.invitation_hasher.digest(body.token)
        session_id = new_id()
        session_token = random_token(32)
        session_digest = services.session_hasher.digest(session_token)
        expires_at = _now() + timedelta(hours=12)
        with services.db.pool.connection() as conn, conn.transaction():
            row = conn.execute(
                "SELECT * FROM portal.rpc_consume_invitation(%s,%s,%s,%s)",
                (invitation_digest, session_id, session_digest, expires_at),
            ).fetchone()
            if row is None:
                raise _problem(401, "invalid_or_expired_invitation")
        csrf = random_token(24)
        set_session_cookies(
            response,
            session_token=session_token,
            csrf_token=csrf,
            secure=services.settings.secure_cookies,
        )
        return {"session_id": session_id, "totp_enrolled": bool(row["totp_enrolled"])}

    @app.post("/v1/auth/logout", status_code=204)
    def logout(
        response: Response,
        context: tuple[Any, DatabaseActor] = Depends(actor_tx),
        services: Services = Depends(svc),
    ) -> Response:
        conn, _ = context
        conn.execute("SELECT portal.rpc_logout()")
        clear_session_cookies(response, secure=services.settings.secure_cookies)
        return response

    @app.post("/v1/auth/totp/enroll")
    def enroll_totp(
        context: tuple[Any, DatabaseActor] = Depends(actor_tx),
        services: Services = Depends(svc),
    ) -> dict[str, str]:
        conn, actor = context
        secret = generate_totp_secret()
        encrypted = services.vault.encrypt(
            secret.encode(), context={"user_id": actor.user_id, "purpose": "portal_totp_v1"}
        )
        conn.execute("SELECT portal.rpc_begin_totp_enrollment(%s)", (encrypted,))
        return {
            "secret": secret,
            "provisioning_uri": provisioning_uri(secret=secret, email="portal-user", issuer="Gordon Greco"),
        }

    def _verify_totp_and_update(
        *, conn: Any, actor: DatabaseActor, code: str, services: Services, confirm: bool
    ) -> list[str]:
        row = conn.execute("SELECT * FROM portal.get_totp_material_for_current_user()").fetchone()
        if row is None or not row["totp_ciphertext"]:
            raise _problem(409, "totp_not_enrolled")
        secret = services.vault.decrypt(
            row["totp_ciphertext"],
            context={"user_id": actor.user_id, "purpose": "portal_totp_v1"},
        ).decode()
        try:
            counter = verify_totp(
                secret,
                code,
                now=_now(),
                last_counter=int(row["totp_last_counter"]),
            )
        except Exception as exc:
            raise _problem(401, "invalid_or_replayed_totp") from exc
        until = _now() + timedelta(minutes=15)
        if not confirm:
            conn.execute("SELECT portal.rpc_step_up_totp(%s,%s)", (counter, until))
            return []
        plain_codes = [random_recovery_code() for _ in range(10)]
        digests = [services.recovery_hasher.digest(code.upper()) for code in plain_codes]
        conn.execute("SELECT portal.rpc_confirm_totp(%s,%s,%s)", (counter, until, digests))
        return plain_codes

    @app.post("/v1/auth/totp/confirm")
    def confirm_totp(
        body: TotpCode,
        context: tuple[Any, DatabaseActor] = Depends(actor_tx),
        services: Services = Depends(svc),
    ) -> dict[str, object]:
        conn, actor = context
        codes = _verify_totp_and_update(
            conn=conn, actor=actor, code=body.code, services=services, confirm=True
        )
        return {"step_up": True, "recovery_codes": codes}

    @app.post("/v1/auth/totp/step-up")
    def step_up_totp(
        body: TotpCode,
        context: tuple[Any, DatabaseActor] = Depends(actor_tx),
        services: Services = Depends(svc),
    ) -> dict[str, bool]:
        conn, actor = context
        _verify_totp_and_update(
            conn=conn, actor=actor, code=body.code, services=services, confirm=False
        )
        return {"step_up": True}

    @app.post("/v1/auth/recovery")
    def recover_session(
        body: RecoveryCodeInput,
        context: tuple[Any, DatabaseActor] = Depends(actor_tx),
        services: Services = Depends(svc),
    ) -> dict[str, bool]:
        conn, _ = context
        digest = services.recovery_hasher.digest(body.recovery_code.strip().upper())
        row = conn.execute(
            "SELECT portal.rpc_use_recovery_code(%s,%s) AS used",
            (digest, _now() + timedelta(minutes=5)),
        ).fetchone()
        if not row or not row["used"]:
            raise _problem(401, "invalid_recovery_code")
        return {"step_up": True}

    @app.get("/v1/me")
    def me(context: tuple[Any, DatabaseActor] = Depends(actor_tx)) -> dict[str, object]:
        conn, actor = context
        user = conn.execute(
            "SELECT id, email, display_name, totp_confirmed_at FROM portal.users WHERE id = portal.current_user_id()"
        ).fetchone()
        return {
            "user": _serialize(user),
            "role": actor.role,
            "household_ids": list(actor.household_ids),
            "entity_ids": list(actor.entity_ids),
            "step_up": actor.auth_level >= 2 and actor.step_up_until and actor.step_up_until > _now(),
        }

    @app.post("/v1/advisor/invitations", status_code=201)
    def invite(
        body: InviteInput,
        context: tuple[Any, DatabaseActor] = Depends(actor_tx),
        services: Services = Depends(svc),
    ) -> dict[str, object]:
        conn, actor = context
        require_role(actor, "advisor")
        require_step_up(actor)
        invitation_id = new_id()
        token = random_token(32)
        digest = services.invitation_hasher.digest(token)
        ciphertext = services.vault.encrypt(
            token.encode(), context={"purpose": "invitation", "token_id": invitation_id}
        )
        expires_at = _now() + timedelta(days=body.expires_in_days)
        row = conn.execute(
            "SELECT * FROM portal.rpc_invite_user(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                invitation_id,
                normalize_email(body.email),
                body.display_name,
                body.household_id,
                body.role,
                body.entity_ids,
                digest,
                ciphertext,
                expires_at,
            ),
        ).fetchone()
        return _serialize(row)

    @app.post("/v1/advisor/revocations", status_code=204)
    def revoke(
        body: RevokeInput,
        context: tuple[Any, DatabaseActor] = Depends(actor_tx),
    ) -> Response:
        conn, actor = context
        require_role(actor, "advisor")
        require_step_up(actor)
        conn.execute(
            "SELECT portal.rpc_revoke_membership(%s,%s,%s)",
            (body.user_id, body.household_id, body.reason),
        )
        return Response(status_code=204)

    @app.get("/v1/document-requests")
    def list_document_requests(
        context: tuple[Any, DatabaseActor] = Depends(actor_tx),
    ) -> dict[str, object]:
        conn, _ = context
        rows = conn.execute(
            """
            SELECT id, household_id, entity_id, title, description, due_at, status, created_at
            FROM portal.document_requests
            WHERE deleted_at IS NULL
            ORDER BY CASE status WHEN 'missing' THEN 0 WHEN 'quarantined' THEN 1 ELSE 2 END, due_at NULLS LAST
            """
        ).fetchall()
        documents = conn.execute(
            """
            SELECT id, request_id, state, original_filename, authoritative_size,
                   authoritative_content_type, created_at, updated_at, review_note
            FROM portal.documents
            WHERE deleted_at IS NULL
            ORDER BY created_at DESC
            """
        ).fetchall()
        return {"requests": _serialize(rows), "documents": _serialize(documents)}

    @app.post("/v1/advisor/document-requests", status_code=201)
    def create_document_request(
        body: DocumentRequestInput,
        context: tuple[Any, DatabaseActor] = Depends(actor_tx),
    ) -> dict[str, object]:
        conn, actor = context
        require_role(actor, "advisor", "operations")
        row = conn.execute(
            "SELECT * FROM portal.rpc_create_document_request(%s,%s,%s,%s,%s)",
            (body.household_id, body.entity_id, body.title, body.description, body.due_at),
        ).fetchone()
        return _serialize(row)

    @app.post("/v1/uploads", status_code=201)
    def begin_upload(
        body: UploadBeginInput,
        context: tuple[Any, DatabaseActor] = Depends(actor_tx),
        services: Services = Depends(svc),
    ) -> dict[str, object]:
        conn, actor = context
        if body.size > services.settings.max_document_bytes:
            raise _problem(422, "document_too_large")
        row = conn.execute(
            "SELECT * FROM portal.rpc_begin_upload(%s,%s,%s,%s,%s)",
            (body.request_id, body.filename, body.content_type, body.size, body.idempotency_key),
        ).fetchone()
        try:
            multipart_id = services.s3.create_multipart(
                bucket=services.settings.quarantine_bucket,
                key=row["object_key"],
                content_type="application/octet-stream",
            )
            conn.execute(
                "SELECT portal.rpc_attach_multipart(%s,%s)",
                (row["upload_id"], multipart_id),
            )
        except Exception:
            conn.execute("SELECT portal.rpc_abort_upload(%s,%s)", (row["upload_id"], "object_store_init_failed"))
            raise
        return {**_serialize(row), "multipart_attached": True, "actor_id": actor.user_id}

    @app.post("/v1/uploads/{upload_id}/parts/{part_number}/capability")
    def sign_upload_part(
        upload_id: str,
        part_number: int,
        context: tuple[Any, DatabaseActor] = Depends(actor_tx),
        services: Services = Depends(svc),
    ) -> dict[str, object]:
        conn, actor = context
        row = conn.execute("SELECT * FROM portal.rpc_get_upload_for_part(%s,%s)", (upload_id, part_number)).fetchone()
        capability = services.capabilities.issue(
            now=_now(),
            actor_id=actor.user_id,
            household_id=str(row["household_id"]),
            resource_id=upload_id,
            bucket=services.settings.quarantine_bucket,
            object_key=str(row["object_key"]),
            method="PUT",
            ttl=timedelta(minutes=5),
            max_bytes=min(8 * 1024 * 1024, services.settings.max_document_bytes),
            part_number=part_number,
        )
        return {"capability": capability.token, "expires_at": capability.expires_at.isoformat()}

    @app.put("/v1/uploads/{upload_id}/parts/{part_number}")
    async def put_upload_part(
        upload_id: str,
        part_number: int,
        request: Request,
        context: tuple[Any, DatabaseActor] = Depends(actor_tx),
        services: Services = Depends(svc),
    ) -> dict[str, object]:
        conn, actor = context
        row = conn.execute("SELECT * FROM portal.rpc_get_upload_for_part(%s,%s)", (upload_id, part_number)).fetchone()
        cap = request.headers.get("x-upload-capability", "")
        max_part = min(8 * 1024 * 1024, services.settings.max_document_bytes)
        chunks: list[bytes] = []
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > max_part:
                raise _problem(413, "upload_part_too_large")
            chunks.append(chunk)
        if size == 0:
            raise _problem(422, "empty_upload_part")
        services.capabilities.verify(
            cap,
            now=_now(),
            actor_id=actor.user_id,
            household_id=str(row["household_id"]),
            resource_id=upload_id,
            bucket=services.settings.quarantine_bucket,
            object_key=str(row["object_key"]),
            method="PUT",
            content_length=size,
            part_number=part_number,
        )
        etag = services.s3.put_part(
            bucket=services.settings.quarantine_bucket,
            key=row["object_key"],
            upload_id=row["multipart_upload_id"],
            part_number=part_number,
            data=b"".join(chunks),
        )
        progress = conn.execute(
            "SELECT * FROM portal.rpc_record_upload_part(%s,%s,%s,%s)",
            (upload_id, part_number, etag, size),
        ).fetchone()
        return _serialize(progress)

    @app.get("/v1/uploads/{upload_id}")
    def resume_upload(
        upload_id: str,
        context: tuple[Any, DatabaseActor] = Depends(actor_tx),
        services: Services = Depends(svc),
    ) -> dict[str, object]:
        conn, _ = context
        row = conn.execute("SELECT * FROM portal.rpc_get_upload(%s)", (upload_id,)).fetchone()
        remote_parts = services.s3.list_parts(
            bucket=services.settings.quarantine_bucket,
            key=row["object_key"],
            upload_id=row["multipart_upload_id"],
        ) if row["state"] == "open" and row["multipart_upload_id"] else []
        return {**_serialize(row), "remote_parts": remote_parts}

    @app.post("/v1/uploads/{upload_id}/complete")
    def complete_upload(
        upload_id: str,
        body: UploadCompleteInput,
        context: tuple[Any, DatabaseActor] = Depends(actor_tx),
        services: Services = Depends(svc),
    ) -> dict[str, object]:
        conn, _ = context
        row = conn.execute("SELECT * FROM portal.rpc_get_upload(%s)", (upload_id,)).fetchone()
        parts = [(int(item["part_number"]), str(item["etag"])) for item in body.parts]
        services.s3.complete_multipart(
            bucket=services.settings.quarantine_bucket,
            key=row["object_key"],
            upload_id=row["multipart_upload_id"],
            parts=parts,
        )
        digest, size = services.s3.authoritative_sha256(
            bucket=services.settings.quarantine_bucket,
            key=row["object_key"],
            max_bytes=services.settings.max_document_bytes,
        )
        completed = conn.execute(
            "SELECT * FROM portal.rpc_complete_upload(%s,%s,%s)",
            (upload_id, size, digest),
        ).fetchone()
        return _serialize(completed)

    @app.post("/v1/support", status_code=201)
    def support(
        body: SupportInput,
        context: tuple[Any, DatabaseActor] = Depends(actor_tx),
    ) -> dict[str, object]:
        conn, actor = context
        require_role(actor, "client")
        row = conn.execute("SELECT * FROM portal.rpc_open_support_request(%s)", (body.message,)).fetchone()
        return _serialize(row)

    @app.post("/v1/advisor/documents/{document_id}/review")
    def review_document(
        document_id: str,
        body: ReviewInput,
        context: tuple[Any, DatabaseActor] = Depends(actor_tx),
    ) -> dict[str, object]:
        conn, actor = context
        require_role(actor, "advisor", "operations")
        row = conn.execute(
            "SELECT * FROM portal.rpc_review_document(%s,%s,%s,%s)",
            (document_id, body.decision, body.note, body.expected_revision),
        ).fetchone()
        return _serialize(row)

    @app.get("/v1/advisor/documents/{document_id}/download")
    def download_document(
        document_id: str,
        context: tuple[Any, DatabaseActor] = Depends(actor_tx),
        services: Services = Depends(svc),
    ) -> dict[str, object]:
        conn, actor = context
        require_role(actor, "advisor", "operations")
        require_step_up(actor)
        row = conn.execute("SELECT * FROM portal.rpc_authorize_document_download(%s)", (document_id,)).fetchone()
        url = services.s3.presign_get(
            bucket=services.settings.clean_bucket,
            key=row["clean_key"],
            expires_seconds=60,
            filename=row["original_filename"],
        )
        return {"url": url, "expires_in": 60, "sha256": row["authoritative_sha256"], "size": row["authoritative_size"]}

    @app.post("/v1/advisor/documents/{document_id}/delete")
    def delete_document(
        document_id: str,
        body: DeleteInput,
        context: tuple[Any, DatabaseActor] = Depends(actor_tx),
    ) -> dict[str, object]:
        conn, actor = context
        require_role(actor, "advisor")
        require_step_up(actor)
        row = conn.execute(
            "SELECT * FROM portal.rpc_request_document_delete(%s,%s,%s)",
            (document_id, body.reason, body.expected_revision),
        ).fetchone()
        return _serialize(row)

    @app.post("/v1/treasury/policies", status_code=201)
    def propose_policy(
        body: PolicyInput,
        context: tuple[Any, DatabaseActor] = Depends(actor_tx),
    ) -> dict[str, object]:
        conn, actor = context
        require_role(actor, "advisor")
        require_step_up(actor)
        row = conn.execute(
            "SELECT * FROM portal.rpc_propose_treasury_policy(%s,%s,%s,%s,%s,%s,%s)",
            (
                body.household_id,
                body.base_version_id,
                body.effective_at,
                body.terms,
                body.signer_user_ids,
                body.approval_threshold,
                body.idempotency_key,
            ),
        ).fetchone()
        return _serialize(row)

    @app.post("/v1/treasury/policies/{policy_id}/approve")
    def approve_policy(
        policy_id: str,
        body: ApprovalInput,
        context: tuple[Any, DatabaseActor] = Depends(actor_tx),
    ) -> dict[str, object]:
        conn, actor = context
        require_step_up(actor)
        row = conn.execute(
            "SELECT * FROM portal.rpc_approve_treasury_policy(%s,%s)",
            (policy_id, body.expected_revision),
        ).fetchone()
        return _serialize(row)

    @app.post("/v1/treasury/cash-operations", status_code=201)
    def request_cash_operation(
        body: CashOperationInput,
        context: tuple[Any, DatabaseActor] = Depends(actor_tx),
    ) -> dict[str, object]:
        conn, _ = context
        row = conn.execute(
            "SELECT * FROM portal.rpc_request_cash_operation(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                body.household_id,
                body.entity_id,
                body.policy_version_id,
                body.operation_type,
                body.amount_minor,
                body.currency.upper(),
                body.requested_effective_at,
                body.rationale,
                body.conflict_key,
                body.idempotency_key,
            ),
        ).fetchone()
        return _serialize(row)

    @app.post("/v1/treasury/cash-operations/{operation_id}/approve")
    def approve_cash_operation(
        operation_id: str,
        body: ApprovalInput,
        context: tuple[Any, DatabaseActor] = Depends(actor_tx),
    ) -> dict[str, object]:
        conn, actor = context
        require_step_up(actor)
        row = conn.execute(
            "SELECT * FROM portal.rpc_approve_cash_operation(%s,%s)",
            (operation_id, body.expected_revision),
        ).fetchone()
        return _serialize(row)

    @app.get("/v1/treasury")
    def treasury_state(context: tuple[Any, DatabaseActor] = Depends(actor_tx)) -> dict[str, object]:
        conn, _ = context
        policies = conn.execute(
            "SELECT * FROM portal.treasury_policy_versions ORDER BY household_id, version DESC"
        ).fetchall()
        operations = conn.execute(
            "SELECT * FROM portal.cash_operations ORDER BY created_at DESC"
        ).fetchall()
        return {"policies": _serialize(policies), "cash_operations": _serialize(operations)}

    return app


__all__ = ["create_app"]
