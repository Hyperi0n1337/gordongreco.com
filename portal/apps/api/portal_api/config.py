from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    environment: str
    portal_base_url: str
    database_url: str
    session_hmac_key: bytes
    invitation_hmac_key: bytes
    capability_hmac_key: bytes
    allowed_origins: tuple[str, ...]
    aws_region: str
    kms_key_id: str
    vault_mode: str
    local_vault_key: str
    s3_endpoint_url: str | None
    quarantine_bucket: str
    clean_bucket: str
    max_document_bytes: int
    secure_cookies: bool

    @classmethod
    def from_env(cls) -> "Settings":
        environment = os.getenv("PORTAL_ENV", "development").strip().lower()

        def secret(name: str) -> bytes:
            value = os.getenv(name, "")
            if len(value.encode()) < 32:
                raise RuntimeError(f"{name} must contain at least 32 bytes")
            return value.encode()

        origins = tuple(
            item.strip().rstrip("/")
            for item in os.getenv("ALLOWED_ORIGINS", "https://portal.example.test").split(",")
            if item.strip()
        )
        vault_mode = os.getenv("VAULT_MODE", "kms" if environment == "production" else "local")
        if environment == "production" and vault_mode != "kms":
            raise RuntimeError("production requires VAULT_MODE=kms")
        return cls(
            environment=environment,
            portal_base_url=os.getenv("PORTAL_BASE_URL", "https://portal.example.test").rstrip("/"),
            database_url=os.environ["DATABASE_URL"],
            session_hmac_key=secret("SESSION_HMAC_KEY"),
            invitation_hmac_key=secret("INVITATION_HMAC_KEY"),
            capability_hmac_key=secret("CAPABILITY_HMAC_KEY"),
            allowed_origins=origins,
            aws_region=os.getenv("AWS_REGION", "us-east-1"),
            kms_key_id=os.getenv("KMS_KEY_ID", ""),
            vault_mode=vault_mode,
            local_vault_key=os.getenv("LOCAL_VAULT_KEY", ""),
            s3_endpoint_url=os.getenv("S3_ENDPOINT_URL") or None,
            quarantine_bucket=os.getenv("QUARANTINE_BUCKET", "gg-portal-quarantine"),
            clean_bucket=os.getenv("CLEAN_BUCKET", "gg-portal-clean"),
            max_document_bytes=int(os.getenv("MAX_DOCUMENT_BYTES", str(25 * 1024 * 1024))),
            secure_cookies=os.getenv("SECURE_COOKIES", "true").lower() == "true",
        )
