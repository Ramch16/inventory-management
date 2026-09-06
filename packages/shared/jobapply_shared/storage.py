"""Object storage abstraction.

``LocalFilesystemStorage`` is the development default so the platform runs with no
cloud account. ``S3Storage`` targets any S3-compatible endpoint (AWS S3, MinIO).
"""

from __future__ import annotations

import mimetypes
import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from jobapply_shared.errors import NotFoundError


@dataclass(frozen=True)
class StoredObject:
    key: str
    size: int
    content_type: str


class ObjectStorage(Protocol):
    def put(self, key: str, data: bytes, content_type: str | None = None) -> StoredObject: ...
    def get(self, key: str) -> bytes: ...
    def presign(self, key: str, expires_in: int = 900) -> str: ...
    def delete(self, key: str) -> None: ...
    def exists(self, key: str) -> bool: ...


def build_key(*parts: str, filename: str) -> str:
    """Random, non-guessable storage key that still sorts by owner."""
    suffix = Path(filename).suffix.lower()[:10]
    return "/".join([*parts, f"{uuid.uuid4().hex}{suffix}"])


class LocalFilesystemStorage:
    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        candidate = (self.root / key).resolve()
        if not str(candidate).startswith(str(self.root)):
            raise ValueError("Storage key escapes the storage root")
        return candidate

    def put(self, key: str, data: bytes, content_type: str | None = None) -> StoredObject:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        guessed = content_type or mimetypes.guess_type(key)[0] or "application/octet-stream"
        return StoredObject(key=key, size=len(data), content_type=guessed)

    def get(self, key: str) -> bytes:
        path = self._path(key)
        if not path.exists():
            raise NotFoundError(f"Object not found: {key}", code="object_not_found")
        return path.read_bytes()

    def presign(self, key: str, expires_in: int = 900) -> str:
        # The API streams local objects through an authenticated download endpoint;
        # there is no public URL in local mode.
        return f"/api/v1/files/{key}"

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        elif path.exists():
            os.remove(path)

    def exists(self, key: str) -> bool:
        return self._path(key).exists()


class S3Storage:
    def __init__(
        self,
        bucket: str,
        *,
        region: str = "us-east-1",
        endpoint_url: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
    ) -> None:
        import boto3

        self.bucket = bucket
        self._client = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

    def put(self, key: str, data: bytes, content_type: str | None = None) -> StoredObject:
        guessed = content_type or mimetypes.guess_type(key)[0] or "application/octet-stream"
        self._client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=guessed,
            ServerSideEncryption="AES256",
        )
        return StoredObject(key=key, size=len(data), content_type=guessed)

    def get(self, key: str) -> bytes:
        response = self._client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read()

    def presign(self, key: str, expires_in: int = 900) -> str:
        return self._client.generate_presigned_url(
            "get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=expires_in
        )

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self.bucket, Key=key)

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self._client.head_object(Bucket=self.bucket, Key=key)
        except ClientError:
            return False
        return True


def build_storage(settings: object) -> ObjectStorage:
    backend = getattr(settings, "storage_backend", "local")
    if backend == "s3":
        bucket = getattr(settings, "aws_s3_bucket", None)
        if not bucket:
            raise ValueError("AWS_S3_BUCKET is required when STORAGE_BACKEND=s3")
        return S3Storage(
            bucket,
            region=getattr(settings, "aws_region", "us-east-1"),
            endpoint_url=getattr(settings, "aws_s3_endpoint_url", None),
            access_key=getattr(settings, "aws_access_key_id", None),
            secret_key=getattr(settings, "aws_secret_access_key", None),
        )
    return LocalFilesystemStorage(getattr(settings, "storage_local_root", "./.storage"))
