from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .errors import Forbidden, ValidationError
from .ids import new_id
from .security import JsonCapabilityCodec


@dataclass(frozen=True)
class Capability:
    token: str
    expires_at: datetime


class CapabilitySigner:
    """Issues narrowly scoped, short-lived object capabilities.

    A capability is bound to actor, household, upload/document, bucket, key,
    HTTP method, optional part number, and maximum bytes. It cannot widen scope.
    """

    def __init__(self, key: bytes) -> None:
        self._codec = JsonCapabilityCodec(key)

    def issue(
        self,
        *,
        now: datetime,
        actor_id: str,
        household_id: str,
        resource_id: str,
        bucket: str,
        object_key: str,
        method: str,
        ttl: timedelta = timedelta(minutes=5),
        max_bytes: int | None = None,
        part_number: int | None = None,
    ) -> Capability:
        if ttl <= timedelta(0) or ttl > timedelta(minutes=10):
            raise ValidationError("capability TTL must be between 1 second and 10 minutes")
        expires_at = now + ttl
        payload: dict[str, object] = {
            "v": 1,
            "jti": new_id(),
            "sub": actor_id,
            "hh": household_id,
            "rid": resource_id,
            "bucket": bucket,
            "key": object_key,
            "method": method.upper(),
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
        }
        if max_bytes is not None:
            payload["max"] = max_bytes
        if part_number is not None:
            payload["part"] = part_number
        return Capability(self._codec.encode(payload), expires_at)

    def verify(
        self,
        token: str,
        *,
        now: datetime,
        actor_id: str,
        household_id: str,
        resource_id: str,
        bucket: str,
        object_key: str,
        method: str,
        content_length: int | None = None,
        part_number: int | None = None,
    ) -> dict[str, object]:
        payload = self._codec.decode(token, now=now)
        expected = {
            "sub": actor_id,
            "hh": household_id,
            "rid": resource_id,
            "bucket": bucket,
            "key": object_key,
            "method": method.upper(),
        }
        for field, value in expected.items():
            if payload.get(field) != value:
                raise Forbidden(f"capability is not valid for {field}")
        if part_number is not None and payload.get("part") != part_number:
            raise Forbidden("capability is not valid for this part")
        if content_length is not None and int(payload.get("max", content_length)) < content_length:
            raise Forbidden("capability byte limit exceeded")
        return payload
