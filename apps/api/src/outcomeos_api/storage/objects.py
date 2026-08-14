from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol, cast
from uuid import UUID

import boto3
from botocore.client import BaseClient
from botocore.exceptions import ClientError


@dataclass(frozen=True)
class ObjectHead:
    length: int
    sha256: str


@dataclass(frozen=True)
class ObjectPage:
    keys: tuple[str, ...]
    cursor: str | None


class ObjectStorage(Protocol):
    def put_if_absent(self, tenant_id: UUID, key: str, body: bytes, sha256: str) -> ObjectHead: ...
    def read(self, tenant_id: UUID, key: str) -> bytes: ...
    def head(self, tenant_id: UUID, key: str) -> ObjectHead: ...
    def delete(self, tenant_id: UUID, key: str) -> None: ...


class PaginatedObjectStorage(ObjectStorage, Protocol):
    """Object-storage port used by tenant-bounded reconciliation scans."""

    def list_page(
        self, tenant_id: UUID, *, cursor: str | None = None, limit: int = 100
    ) -> ObjectPage: ...


def _object_key(tenant_id: UUID, key: str) -> str:
    if not key or key.startswith("/") or ".." in key.split("/"):
        raise ValueError("object key must be a safe relative key")
    return f"tenants/{tenant_id}/{key}"


class S3ObjectStorage:
    """Bounded S3-compatible storage with tenant-prefixed keys and conditional creates."""

    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str,
        access_key_id: str,
        secret_access_key: str,
        max_bytes: int,
        client: BaseClient | None = None,
    ) -> None:
        if max_bytes < 1:
            raise ValueError("max_bytes must be positive")
        self._bucket = bucket
        self._max_bytes = max_bytes
        self._client = client or boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
        )

    def put_if_absent(self, tenant_id: UUID, key: str, body: bytes, sha256: str) -> ObjectHead:
        if len(body) > self._max_bytes:
            raise ValueError("object exceeds configured byte limit")
        actual = hashlib.sha256(body).hexdigest()
        if actual != sha256:
            raise ValueError("object digest mismatch")
        try:
            self._client.put_object(
                Bucket=self._bucket,
                Key=_object_key(tenant_id, key),
                Body=body,
                ContentLength=len(body),
                Metadata={"sha256": actual},
                IfNoneMatch="*",
                ServerSideEncryption="AES256",
            )
        except ClientError as error:
            status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            if status in {409, 412}:
                existing = self.head(tenant_id, key)
                if existing != ObjectHead(len(body), actual):
                    raise ValueError("object key already exists with different content") from error
                return existing
            raise
        return ObjectHead(len(body), actual)

    def read(self, tenant_id: UUID, key: str) -> bytes:
        response = self._client.get_object(Bucket=self._bucket, Key=_object_key(tenant_id, key))
        length = int(response["ContentLength"])
        if length > self._max_bytes:
            raise ValueError("stored object exceeds configured byte limit")
        body = cast(bytes, response["Body"].read(self._max_bytes + 1))
        if len(body) != length or len(body) > self._max_bytes:
            raise ValueError("stored object length mismatch")
        expected = response.get("Metadata", {}).get("sha256")
        if not expected or hashlib.sha256(body).hexdigest() != expected:
            raise ValueError("stored object digest mismatch")
        return body

    def head(self, tenant_id: UUID, key: str) -> ObjectHead:
        response = self._client.head_object(Bucket=self._bucket, Key=_object_key(tenant_id, key))
        digest = response.get("Metadata", {}).get("sha256")
        if not digest:
            raise ValueError("stored object has no digest metadata")
        return ObjectHead(int(response["ContentLength"]), digest)

    def delete(self, tenant_id: UUID, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=_object_key(tenant_id, key))

    def list_page(
        self, tenant_id: UUID, *, cursor: str | None = None, limit: int = 100
    ) -> ObjectPage:
        if limit < 1 or limit > 1000:
            raise ValueError("object listing limit must be between 1 and 1000")
        prefix = f"tenants/{tenant_id}/"
        request: dict[str, object] = {
            "Bucket": self._bucket,
            "Prefix": prefix,
            "MaxKeys": limit,
        }
        if cursor:
            request["ContinuationToken"] = cursor
        response = self._client.list_objects_v2(**request)
        keys = tuple(
            str(item["Key"])[len(prefix) :]
            for item in response.get("Contents", [])
            if str(item.get("Key", "")).startswith(prefix)
        )
        next_cursor = response.get("NextContinuationToken")
        return ObjectPage(keys, str(next_cursor) if next_cursor else None)
