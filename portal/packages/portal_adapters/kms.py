from __future__ import annotations

import base64


class AwsKmsVault:
    """Envelope-free KMS encryption for small TOTP secrets.

    The encryption context binds ciphertext to the portal user and purpose.
    IAM must permit Encrypt/Decrypt only on the configured CMK.
    """

    def __init__(self, *, key_id: str, region_name: str, endpoint_url: str | None = None) -> None:
        import boto3

        self.key_id = key_id
        self.client = boto3.client("kms", region_name=region_name, endpoint_url=endpoint_url or None)

    def encrypt(self, plaintext: bytes, *, context: dict[str, str]) -> str:
        response = self.client.encrypt(
            KeyId=self.key_id,
            Plaintext=plaintext,
            EncryptionContext=context,
            EncryptionAlgorithm="SYMMETRIC_DEFAULT",
        )
        return base64.b64encode(response["CiphertextBlob"]).decode("ascii")

    def decrypt(self, ciphertext: str, *, context: dict[str, str]) -> bytes:
        response = self.client.decrypt(
            CiphertextBlob=base64.b64decode(ciphertext),
            EncryptionContext=context,
            EncryptionAlgorithm="SYMMETRIC_DEFAULT",
        )
        return bytes(response["Plaintext"])
