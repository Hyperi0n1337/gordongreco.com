from __future__ import annotations

import hmac
from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        response = await call_next(request)
        response.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'; base-uri 'none'")
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("Pragma", "no-cache")
        return response


def require_origin(request: Request, allowed_origins: tuple[str, ...]) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    origin = request.headers.get("origin")
    if not origin or origin.rstrip("/") not in allowed_origins:
        raise HTTPException(status_code=403, detail={"code": "origin_denied"})


def require_csrf(request: Request) -> None:
    cookie = request.cookies.get("gg_csrf", "")
    header = request.headers.get("x-csrf-token", "")
    if not cookie or not header or not hmac.compare_digest(cookie, header):
        raise HTTPException(status_code=403, detail={"code": "csrf_denied"})


def set_session_cookies(response: Response, *, session_token: str, csrf_token: str, secure: bool) -> None:
    response.set_cookie(
        "gg_session",
        session_token,
        httponly=True,
        secure=secure,
        samesite="strict",
        path="/",
        max_age=12 * 60 * 60,
    )
    response.set_cookie(
        "gg_csrf",
        csrf_token,
        httponly=False,
        secure=secure,
        samesite="strict",
        path="/",
        max_age=12 * 60 * 60,
    )


def clear_session_cookies(response: Response, *, secure: bool) -> None:
    response.delete_cookie("gg_session", path="/", secure=secure, samesite="strict")
    response.delete_cookie("gg_csrf", path="/", secure=secure, samesite="strict")
