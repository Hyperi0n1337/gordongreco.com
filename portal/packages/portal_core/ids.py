from __future__ import annotations

import base64
import secrets
import uuid


def new_id() -> str:
    return str(uuid.uuid4())


def random_token(nbytes: int = 32) -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(nbytes)).rstrip(b"=").decode("ascii")


def random_recovery_code() -> str:
    raw = base64.b32encode(secrets.token_bytes(10)).decode("ascii").rstrip("=")
    return f"{raw[:5]}-{raw[5:10]}-{raw[10:15]}-{raw[15:]}"
