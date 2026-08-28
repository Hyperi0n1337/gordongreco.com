from __future__ import annotations

import base64
import json
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class LocalAesGcmVault:
    """Development-only vault. Production configuration rejects this adapter."""

    def __init__(self, key_b64: str) -> None:
        key = base64.urlsafe_b64decode(key_b64 + "=" * (-len(key_b64) % 4))
        if len(key) != 32:
            raise ValueError("LOCAL_VAULT_KEY must decode to exactly 32 bytes")
        self._cipher = AESGCM(key)

    @staticmethod
    def _aad(context: dict[str, str]) -> bytes:
        return json.dumps(context, sort_keys=True, separators=(",", ":")).encode()

    def encrypt(self, plaintext: bytes, *, context: dict[str, str]) -> str:
        nonce = os.urandom(12)
        encrypted = self._cipher.encrypt(nonce, plaintext, self._aad(context))
        return base64.urlsafe_b64encode(nonce + encrypted).decode("ascii")

    def decrypt(self, ciphertext: str, *, context: dict[str, str]) -> bytes:
        raw = base64.urlsafe_b64decode(ciphertext)
        return self._cipher.decrypt(raw[:12], raw[12:], self._aad(context))
