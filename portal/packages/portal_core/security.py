from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import struct
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from urllib.parse import quote

from .errors import Expired, Unauthorized, ValidationError
from .ids import random_token


class SecretVault(Protocol):
    def encrypt(self, plaintext: bytes, *, context: dict[str, str]) -> str: ...
    def decrypt(self, ciphertext: str, *, context: dict[str, str]) -> bytes: ...


class TokenHasher:
    """HMAC token digests prevent useful offline checks after a database leak."""

    def __init__(self, key: bytes, namespace: bytes = b"portal-token-v1") -> None:
        if len(key) < 32:
            raise ValueError("token HMAC key must be at least 32 bytes")
        self._key = key
        self._namespace = namespace

    def digest(self, token: str) -> str:
        return hmac.new(self._key, self._namespace + b"\x00" + token.encode(), hashlib.sha256).hexdigest()

    def matches(self, token: str, digest: str) -> bool:
        return hmac.compare_digest(self.digest(token), digest)


class JsonCapabilityCodec:
    def __init__(self, key: bytes) -> None:
        if len(key) < 32:
            raise ValueError("capability key must be at least 32 bytes")
        self._key = key

    @staticmethod
    def _b64e(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")

    @staticmethod
    def _b64d(value: str) -> bytes:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

    def encode(self, payload: dict[str, object]) -> str:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        body = self._b64e(raw)
        sig = self._b64e(hmac.new(self._key, body.encode(), hashlib.sha256).digest())
        return f"{body}.{sig}"

    def decode(self, token: str, *, now: datetime) -> dict[str, object]:
        try:
            body, supplied = token.split(".", 1)
            expected = self._b64e(hmac.new(self._key, body.encode(), hashlib.sha256).digest())
            if not hmac.compare_digest(expected, supplied):
                raise Unauthorized("invalid capability signature")
            payload = json.loads(self._b64d(body))
        except Unauthorized:
            raise
        except Exception as exc:
            raise Unauthorized("malformed capability") from exc
        exp = int(payload.get("exp", 0))
        if int(now.timestamp()) >= exp:
            raise Expired("capability expired")
        return payload


def normalize_email(email: str) -> str:
    value = email.strip().casefold()
    if len(value) > 254 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
        raise ValidationError("invalid email")
    return value


def generate_totp_secret() -> str:
    raw = base64.b32encode(__import__("secrets").token_bytes(20)).decode("ascii")
    return raw.rstrip("=")


def _b32decode(secret: str) -> bytes:
    compact = secret.replace(" ", "").upper()
    return base64.b32decode(compact + "=" * (-len(compact) % 8), casefold=True)


def totp_counter(timestamp: datetime, period: int = 30) -> int:
    return int(timestamp.timestamp()) // period


def hotp(secret: str, counter: int, digits: int = 6) -> str:
    digest = hmac.new(_b32decode(secret), struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = (struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF) % (10**digits)
    return str(value).zfill(digits)


def verify_totp(
    secret: str,
    code: str,
    *,
    now: datetime,
    last_counter: int = -1,
    window: int = 1,
) -> int:
    if not re.fullmatch(r"\d{6}", code):
        raise Unauthorized("invalid TOTP")
    current = totp_counter(now)
    for counter in range(current - window, current + window + 1):
        if counter <= last_counter:
            continue
        if hmac.compare_digest(hotp(secret, counter), code):
            return counter
    raise Unauthorized("invalid or replayed TOTP")


def provisioning_uri(*, secret: str, email: str, issuer: str = "Gordon Greco") -> str:
    label = quote(f"{issuer}:{email}")
    return f"otpauth://totp/{label}?secret={secret}&issuer={quote(issuer)}&algorithm=SHA1&digits=6&period=30"


def new_session_token() -> str:
    return random_token(32)
