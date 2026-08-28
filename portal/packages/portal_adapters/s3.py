from __future__ import annotations

import hashlib
from collections.abc import Iterable


class S3PrivateObjectStore:
    """S3 adapter for private quarantine and clean buckets.

    The API proxies signed-capability upload parts so it can enforce byte limits;
    no client receives AWS credentials. The worker alone can copy to clean.
    """

    def __init__(self, *, region_name: str, endpoint_url: str | None = None, kms_key_id: str | None = None) -> None:
        import boto3

        self.client = boto3.client("s3", region_name=region_name, endpoint_url=endpoint_url or None)
        self.kms_key_id = kms_key_id

    def _encryption(self) -> dict[str, str]:
        if self.kms_key_id:
            return {"ServerSideEncryption": "aws:kms", "SSEKMSKeyId": self.kms_key_id}
        return {"ServerSideEncryption": "AES256"}

    def create_multipart(self, *, bucket: str, key: str, content_type: str) -> str:
        response = self.client.create_multipart_upload(
            Bucket=bucket,
            Key=key,
            ContentType=content_type,
            Metadata={"portal-state": "quarantine"},
            **self._encryption(),
        )
        return str(response["UploadId"])

    def put_part(self, *, bucket: str, key: str, upload_id: str, part_number: int, data: bytes) -> str:
        response = self.client.upload_part(
            Bucket=bucket,
            Key=key,
            UploadId=upload_id,
            PartNumber=part_number,
            Body=data,
            ChecksumSHA256=__import__("base64").b64encode(hashlib.sha256(data).digest()).decode("ascii"),
        )
        return str(response["ETag"]).strip('"')

    def list_parts(self, *, bucket: str, key: str, upload_id: str) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        marker = 0
        while True:
            response = self.client.list_parts(
                Bucket=bucket,
                Key=key,
                UploadId=upload_id,
                PartNumberMarker=marker,
            )
            for part in response.get("Parts", []):
                rows.append(
                    {
                        "part_number": int(part["PartNumber"]),
                        "etag": str(part["ETag"]).strip('"'),
                        "size": int(part["Size"]),
                    }
                )
            if not response.get("IsTruncated"):
                break
            marker = int(response["NextPartNumberMarker"])
        return rows

    def complete_multipart(
        self,
        *,
        bucket: str,
        key: str,
        upload_id: str,
        parts: Iterable[tuple[int, str]],
    ) -> None:
        ordered = [{"PartNumber": number, "ETag": etag} for number, etag in sorted(parts)]
        self.client.complete_multipart_upload(
            Bucket=bucket,
            Key=key,
            UploadId=upload_id,
            MultipartUpload={"Parts": ordered},
        )

    def abort_multipart(self, *, bucket: str, key: str, upload_id: str) -> None:
        self.client.abort_multipart_upload(Bucket=bucket, Key=key, UploadId=upload_id)

    def head(self, *, bucket: str, key: str) -> dict[str, object]:
        response = self.client.head_object(Bucket=bucket, Key=key)
        return {
            "size": int(response["ContentLength"]),
            "content_type": str(response.get("ContentType") or "application/octet-stream"),
            "etag": str(response.get("ETag") or "").strip('"'),
            "metadata": dict(response.get("Metadata") or {}),
        }

    def read(self, *, bucket: str, key: str, max_bytes: int) -> bytes:
        response = self.client.get_object(Bucket=bucket, Key=key)
        stream = response["Body"]
        body = stream.read(max_bytes + 1)
        if len(body) > max_bytes or stream.read(1):
            raise ValueError("object exceeds maximum bytes")
        return body

    def authoritative_sha256(self, *, bucket: str, key: str, max_bytes: int) -> tuple[str, int]:
        response = self.client.get_object(Bucket=bucket, Key=key)
        digest = hashlib.sha256()
        size = 0
        for chunk in iter(lambda: response["Body"].read(1024 * 1024), b""):
            size += len(chunk)
            if size > max_bytes:
                raise ValueError("object exceeds maximum bytes")
            digest.update(chunk)
        return digest.hexdigest(), size

    def copy_verified(
        self,
        *,
        source_bucket: str,
        source_key: str,
        target_bucket: str,
        target_key: str,
        authoritative_sha256: str,
        authoritative_size: int,
        content_type: str,
    ) -> None:
        self.client.copy_object(
            Bucket=target_bucket,
            Key=target_key,
            CopySource={"Bucket": source_bucket, "Key": source_key},
            MetadataDirective="REPLACE",
            Metadata={
                "portal-state": "clean",
                "authoritative-sha256": authoritative_sha256,
                "authoritative-size": str(authoritative_size),
            },
            ContentType=content_type,
            **self._encryption(),
        )
        head = self.head(bucket=target_bucket, key=target_key)
        if int(head["size"]) != authoritative_size:
            self.delete(bucket=target_bucket, key=target_key)
            raise ValueError("clean copy size mismatch")

    def presign_get(self, *, bucket: str, key: str, expires_seconds: int, filename: str) -> str:
        return str(
            self.client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": bucket,
                    "Key": key,
                    "ResponseContentDisposition": f'attachment; filename="{filename.replace(chr(34), "")}"',
                },
                ExpiresIn=expires_seconds,
            )
        )

    def delete(self, *, bucket: str, key: str) -> None:
        self.client.delete_object(Bucket=bucket, Key=key)
