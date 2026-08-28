"""Run a fictional, loopback-only Gordon Greco portal acceptance demo.

This is deliberately not the production PostgreSQL/S3 runtime. It gives Markos
one browser-verifiable invitation, checklist, upload, quarantine, support, and
logout workflow while keeping all test bytes in process memory.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import os
import re
import secrets
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from pathlib import Path, PurePath
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles


PORTAL_WEB = Path(__file__).resolve().parents[1] / "portal-web"
INVITATION = "ann-demo-invite"
ACCOUNT = {
    "id": "ann-demo.test",
    "email": "ann.terzidis@example.test",
    "display_name": "Ann Terzidis (fictional test account)",
    "totp_confirmed_at": "2026-08-28T00:00:00Z",
}
ACTIVE_ACCOUNT = dict(ACCOUNT)
MAGIC_LINKS: dict[str, dict[str, Any]] = {}
SESSIONS: dict[str, dict[str, Any]] = {}
SEND_TIMES: list[tuple[datetime, str]] = []
ENABLE_REAL_CLIENT_EMAILS = os.getenv("PORTAL_DEMO_ENABLE_REAL_CLIENT_EMAILS", "false").lower() == "true"
PORTAL_PROFILES = {
    "arhra1337@gmail.com": {
        "display_name": "Robert Tharp (test delivery)",
        "household_id": "robert-tharp.test",
        "test_delivery": True,
    },
    "baldleggedcutlet@protonmail.com": {
        "display_name": "Evan Carroll (test delivery)",
        "household_id": "evan-emma-carroll.test",
        "test_delivery": True,
    },
    "roberttharp1818@gmail.com": {
        "display_name": "Robert Tharp",
        "household_id": "robert-tharp",
        "test_delivery": False,
    },
    "evan@bubbleboxprep.com": {
        "display_name": "Evan Carroll",
        "household_id": "evan-emma-carroll",
        "test_delivery": False,
    },
}
REQUESTS = [
    {
        "id": "ann-id-document.test",
        "title": "Identity document",
        "description": "Upload a fictional test PDF, image, text, or CSV file.",
        "due_at": None,
        "status": "missing",
    },
    {
        "id": "ann-account-statement.test",
        "title": "Current account statement",
        "description": "Fictional test request for the document workflow.",
        "due_at": None,
        "status": "missing",
    },
    {
        "id": "ann-beneficiary-review.test",
        "title": "Beneficiary information review",
        "description": "Confirm the checklist presentation; do not upload real records here.",
        "due_at": None,
        "status": "missing",
    },
]
UPLOADS: dict[str, dict[str, Any]] = {}
DOCUMENTS: list[dict[str, Any]] = []
SUPPORT: list[dict[str, str]] = []
INVITATION_CONSUMED = False
ALLOWED_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "text/plain",
    "text/csv",
    "application/csv",
}
ALLOWED_SUFFIXES = {".pdf", ".jpg", ".jpeg", ".png", ".txt", ".csv"}
MAX_BYTES = 25 * 1024 * 1024
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PORTAL_BASE_URL = os.getenv("PORTAL_DEMO_BASE_URL", "http://127.0.0.1:8520").rstrip("/")


def _error(status: int, code: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code})


def _session(request: Request) -> dict[str, Any]:
    token = request.cookies.get("gg_session", "")
    row = SESSIONS.get(token)
    if not row:
        raise _error(401, "session_required")
    return row


def _csrf(request: Request) -> dict[str, Any]:
    session = _session(request)
    cookie = request.cookies.get("gg_csrf", "")
    header = request.headers.get("x-csrf-token", "")
    csrf = session["csrf"]
    if not cookie or not secrets.compare_digest(cookie, csrf) or not secrets.compare_digest(header, csrf):
        raise _error(403, "csrf_failed")
    return session


def _loopback(request: Request) -> None:
    host = request.client.host if request.client else ""
    if host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
        raise _error(403, "loopback_only")


def _normalize_email(value: object) -> str:
    email = str(value or "").strip().lower()
    if len(email) > 254 or not EMAIL_RE.fullmatch(email):
        raise _error(422, "invalid_email")
    return email


def _rate_limit(email: str) -> None:
    now = datetime.now(UTC)
    SEND_TIMES[:] = [(at, recipient) for at, recipient in SEND_TIMES if at > now - timedelta(hours=1)]
    if len(SEND_TIMES) >= 5:
        raise _error(429, "demo_email_rate_limited")
    recent_recipient = sum(
        1 for at, recipient in SEND_TIMES if recipient == email and at > now - timedelta(minutes=15)
    )
    if recent_recipient >= 3:
        raise _error(429, "demo_email_rate_limited")
    SEND_TIMES.append((now, email))


def _deliver_magic_link(*, recipient: str, display_name: str, link: str) -> dict[str, Any]:
    from mas.advisory.email.client_delivery import (
        _send_gmail_message,
        get_sender_profile,
        load_firm_config,
    )

    sender = get_sender_profile("gordon_greco", firm_config=load_firm_config())
    message = EmailMessage()
    message["To"] = recipient
    message["From"] = f"{sender.name} <{sender.email}>"
    message["Subject"] = "Your Gordon Greco secure portal link"
    message.set_content(
        f"Hello {display_name},\n\nOpen your Gordon Greco portal acceptance link:\n\n"
        f"{link}\n\n"
        "This single-use link expires in 10 minutes. Do not upload real documents to the demo."
    )
    safe_link = html.escape(link, quote=True)
    message.add_alternative(
        "<html><body style='font-family:Arial,sans-serif;color:#142640'>"
        f"<h2>Gordon Greco secure portal</h2><p>Hello {html.escape(display_name)},</p>"
        "<p>Open your fictional portal acceptance account with this single-use link:</p>"
        f"<p><a href='{safe_link}' style='display:inline-block;padding:12px 18px;"
        "background:#0f2440;color:#fff;text-decoration:none;border-radius:6px'>"
        "Open secure portal</a></p>"
        "<p>This link expires in 10 minutes. Do not upload real documents to the demo.</p>"
        "</body></html>",
        subtype="html",
    )
    return _send_gmail_message(message, sender)


app = FastAPI(title="Gordon Greco portal demo", docs_url=None, redoc_url=None)


@app.middleware("http")
async def demo_security_headers(request: Request, call_next: Any) -> Response:
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
    )
    return response


@app.get("/")
def home() -> RedirectResponse:
    return RedirectResponse(f"/portal/?invite={INVITATION}", status_code=307)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": "fictional_loopback_demo"}


@app.post("/api/v1/auth/invitation/consume")
async def consume_invitation(request: Request, response: Response) -> dict[str, object]:
    global INVITATION_CONSUMED
    body = await request.json()
    if INVITATION_CONSUMED or not secrets.compare_digest(str(body.get("token") or ""), INVITATION):
        raise _error(401, "invalid_or_expired_invitation")
    INVITATION_CONSUMED = True
    session_token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(24)
    SESSIONS[session_token] = {
        "csrf": csrf,
        "account": dict(ACCOUNT),
        "household_id": "markos-ann-demo.test",
    }
    response.set_cookie("gg_session", session_token, httponly=True, secure=False, samesite="strict", path="/")
    response.set_cookie("gg_csrf", csrf, httponly=False, secure=False, samesite="strict", path="/")
    return {"session_id": "ann-demo-session.test", "totp_enrolled": True}


@app.post("/api/v1/auth/magic-link", status_code=202)
async def magic_link(request: Request) -> dict[str, str]:
    _loopback(request)
    body = await request.json()
    email = _normalize_email(body.get("email"))
    profile = PORTAL_PROFILES.get(email)
    if not profile or (not profile["test_delivery"] and not ENABLE_REAL_CLIENT_EMAILS):
        return {
            "status": "accepted",
            "mode": "fictional_loopback_demo",
            "delivery": "not_eligible",
            "message_id": "",
        }
    _rate_limit(email)
    token = secrets.token_urlsafe(32)
    MAGIC_LINKS[token] = {
        "email": email,
        "profile": profile,
        "expires_at": datetime.now(UTC) + timedelta(minutes=10),
        "used": False,
    }
    link = f"{PORTAL_BASE_URL}/portal/?token={token}"
    try:
        result = _deliver_magic_link(
            recipient=email,
            display_name=str(profile["display_name"]),
            link=link,
        )
    except Exception as exc:
        MAGIC_LINKS.pop(token, None)
        raise _error(503, "email_delivery_failed") from exc
    return {
        "status": "accepted",
        "mode": "fictional_loopback_demo",
        "delivery": "sent",
        "message_id": str(result.get("message_id") or ""),
    }


@app.post("/api/v1/auth/magic-link/consume")
async def consume_magic_link(request: Request, response: Response) -> dict[str, object]:
    _loopback(request)
    body = await request.json()
    token = str(body.get("token") or "")
    row = MAGIC_LINKS.get(token)
    now = datetime.now(UTC)
    if not row or row["used"] or row["expires_at"] <= now:
        raise _error(401, "invalid_or_expired_magic_link")
    row["used"] = True
    account = {
        "id": f"email-demo-{hashlib.sha256(row['email'].encode()).hexdigest()[:16]}.test",
        "email": row["email"],
        "display_name": row["profile"]["display_name"],
        "totp_confirmed_at": now.isoformat(),
    }
    session_token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(24)
    SESSIONS[session_token] = {
        "csrf": csrf,
        "account": account,
        "household_id": row["profile"]["household_id"],
    }
    response.set_cookie("gg_session", session_token, httponly=True, secure=False, samesite="strict", path="/")
    response.set_cookie("gg_csrf", csrf, httponly=False, secure=False, samesite="strict", path="/")
    return {"session_id": "email-demo-session.test", "totp_enrolled": True}


@app.get("/api/v1/me")
def me(request: Request) -> dict[str, object]:
    session = _session(request)
    return {
        "user": session["account"],
        "role": "client",
        "household_ids": [session["household_id"]],
        "entity_ids": [],
        "step_up": True,
    }


@app.get("/api/v1/document-requests")
def document_requests(request: Request) -> dict[str, object]:
    session = _session(request)
    documents = [
        row for row in reversed(DOCUMENTS) if row["household_id"] == session["household_id"]
    ]
    return {"requests": REQUESTS, "documents": documents}


@app.post("/api/v1/uploads", status_code=201)
async def begin_upload(request: Request) -> dict[str, str]:
    session = _csrf(request)
    body = await request.json()
    request_id = str(body.get("request_id") or "")
    filename = PurePath(str(body.get("filename") or "").replace("\\", "/")).name
    content_type = str(body.get("content_type") or "").lower()
    size = int(body.get("size") or 0)
    if request_id not in {row["id"] for row in REQUESTS}:
        raise _error(404, "document_request_not_found")
    if not filename or PurePath(filename).suffix.lower() not in ALLOWED_SUFFIXES:
        raise _error(422, "invalid_filename")
    if content_type not in ALLOWED_TYPES or size <= 0 or size > MAX_BYTES:
        raise _error(422, "invalid_upload")
    upload_id = secrets.token_urlsafe(18)
    UPLOADS[upload_id] = {
        "request_id": request_id,
        "filename": filename,
        "content_type": content_type,
        "declared_size": size,
        "parts": {},
        "state": "open",
        "household_id": session["household_id"],
    }
    return {"upload_id": upload_id}


@app.get("/api/v1/uploads/{upload_id}")
def upload_status(upload_id: str, request: Request) -> dict[str, object]:
    session = _session(request)
    upload = UPLOADS.get(upload_id)
    if not upload or upload["household_id"] != session["household_id"]:
        raise _error(404, "upload_not_found")
    return {
        "state": upload["state"],
        "declared_size": upload["declared_size"],
        "uploaded_bytes": sum(len(value) for value in upload["parts"].values()),
        "remote_parts": [
            {"part_number": number, "size": len(data), "etag": hashlib.sha256(data).hexdigest()[:24]}
            for number, data in sorted(upload["parts"].items())
        ],
    }


@app.post("/api/v1/uploads/{upload_id}/parts/{part_number}/capability")
def part_capability(upload_id: str, part_number: int, request: Request) -> dict[str, str]:
    session = _csrf(request)
    upload = UPLOADS.get(upload_id)
    if not upload or upload["household_id"] != session["household_id"] or not 1 <= part_number <= 10_000:
        raise _error(404, "upload_not_found")
    return {"capability": f"demo:{upload_id}:{part_number}"}


@app.put("/api/v1/uploads/{upload_id}/parts/{part_number}")
async def upload_part(upload_id: str, part_number: int, request: Request) -> dict[str, str]:
    session = _csrf(request)
    upload = UPLOADS.get(upload_id)
    expected = f"demo:{upload_id}:{part_number}"
    if (
        not upload
        or upload["household_id"] != session["household_id"]
        or not secrets.compare_digest(request.headers.get("x-upload-capability", ""), expected)
    ):
        raise _error(403, "invalid_upload_capability")
    data = await request.body()
    if not data or len(data) > 5 * 1024 * 1024:
        raise _error(422, "invalid_upload_part")
    upload["parts"][part_number] = data
    return {"etag": hashlib.sha256(data).hexdigest()[:24]}


@app.post("/api/v1/uploads/{upload_id}/complete")
async def complete_upload(upload_id: str, request: Request) -> dict[str, object]:
    session = _csrf(request)
    upload = UPLOADS.get(upload_id)
    if not upload or upload["household_id"] != session["household_id"] or upload["state"] != "open":
        raise _error(409, "upload_not_open")
    body = await request.json()
    numbers = [int(row.get("part_number")) for row in body.get("parts") or []]
    if not numbers or numbers != sorted(set(numbers)):
        raise _error(422, "invalid_parts")
    try:
        data = b"".join(upload["parts"][number] for number in numbers)
    except KeyError as exc:
        raise _error(409, "missing_upload_part") from exc
    if len(data) != upload["declared_size"]:
        upload["state"] = "rejected"
        raise _error(409, "size_mismatch")
    document = {
        "id": secrets.token_urlsafe(14),
        "request_id": upload["request_id"],
        "original_filename": upload["filename"],
        "state": "quarantined",
        "authoritative_size": len(data),
        "authoritative_sha256": hashlib.sha256(data).hexdigest(),
        "review_note": "Fictional demo upload retained in process memory only.",
        "created_at": datetime.now(UTC).isoformat(),
        "household_id": session["household_id"],
    }
    DOCUMENTS.append(document)
    upload["state"] = "complete"
    return document


@app.post("/api/v1/support", status_code=201)
async def support(request: Request) -> dict[str, str]:
    session = _csrf(request)
    message = str((await request.json()).get("message") or "").strip()
    if not message or len(message) > 500:
        raise _error(422, "invalid_support_request")
    SUPPORT.append(
        {
            "message": message,
            "household_id": session["household_id"],
            "created_at": datetime.now(UTC).isoformat(),
        }
    )
    return {"status": "recorded_in_demo_memory"}


@app.post("/api/v1/auth/logout", status_code=204)
def logout(request: Request, response: Response) -> Response:
    session_token = request.cookies.get("gg_session", "")
    _csrf(request)
    SESSIONS.pop(session_token, None)
    response.delete_cookie("gg_session", path="/")
    response.delete_cookie("gg_csrf", path="/")
    response.status_code = 204
    return response


app.mount("/portal", StaticFiles(directory=PORTAL_WEB, html=True), name="portal")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the fictional loopback Gordon Greco portal demo")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8520)
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("The fictional demo is loopback-only")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
