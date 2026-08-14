from datetime import UTC, datetime, timedelta
from io import BytesIO
from os import urandom
from typing import Any, cast
from uuid import uuid4

import pytest
from botocore.client import BaseClient
from botocore.exceptions import ClientError
from cryptography.exceptions import InvalidTag

from outcomeos_api.integrations.secrets import SecretCipher, rotation_is_usable
from outcomeos_api.storage.objects import S3ObjectStorage, _object_key


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, dict[str, str]]] = {}

    def put_object(self, **kwargs: Any) -> None:
        key = cast(str, kwargs["Key"])
        if key in self.objects:
            raise ClientError(
                {
                    "Error": {"Code": "PreconditionFailed"},
                    "ResponseMetadata": {"HTTPStatusCode": 412},
                },
                "PutObject",
            )
        self.objects[key] = (cast(bytes, kwargs["Body"]), cast(dict[str, str], kwargs["Metadata"]))

    def get_object(self, **kwargs: Any) -> dict[str, Any]:
        body, metadata = self.objects[cast(str, kwargs["Key"])]
        return {"Body": BytesIO(body), "ContentLength": len(body), "Metadata": metadata}

    def head_object(self, **kwargs: Any) -> dict[str, Any]:
        body, metadata = self.objects[cast(str, kwargs["Key"])]
        return {"ContentLength": len(body), "Metadata": metadata}

    def delete_object(self, **kwargs: Any) -> None:
        self.objects.pop(cast(str, kwargs["Key"]), None)


def test_secret_cipher_authenticates_tenant_endpoint_and_version() -> None:
    tenant, endpoint = uuid4(), uuid4()
    cipher = SecretCipher({"current": urandom(32), "old": urandom(32)}, "current")
    encrypted = cipher.encrypt(b"do-not-log", tenant_id=tenant, endpoint_id=endpoint, version=2)
    assert encrypted.key_id == "current"
    assert encrypted.ciphertext != b"do-not-log"
    assert (
        cipher.decrypt(encrypted, tenant_id=tenant, endpoint_id=endpoint, version=2)
        == b"do-not-log"
    )
    with pytest.raises(InvalidTag):
        cipher.decrypt(encrypted, tenant_id=uuid4(), endpoint_id=endpoint, version=2)
    with pytest.raises(InvalidTag):
        cipher.decrypt(encrypted, tenant_id=tenant, endpoint_id=endpoint, version=1)


def test_secret_cipher_rejects_bad_keyring_and_rotation_window() -> None:
    with pytest.raises(ValueError, match="32 bytes"):
        SecretCipher({"bad": b"short"}, "bad")
    now = datetime.now(UTC)
    assert rotation_is_usable(
        not_before=now - timedelta(seconds=1), expires_at=now + timedelta(seconds=1), now=now
    )
    assert not rotation_is_usable(
        not_before=now + timedelta(seconds=1), expires_at=now + timedelta(seconds=2), now=now
    )


def test_object_keys_are_tenant_prefixed_and_reject_traversal() -> None:
    tenant = uuid4()
    assert _object_key(tenant, "raw/event.json") == f"tenants/{tenant}/raw/event.json"
    with pytest.raises(ValueError):
        _object_key(tenant, "../other-tenant")


def test_s3_adapter_checks_limits_digests_duplicates_and_reads() -> None:
    fake = FakeS3()
    storage = S3ObjectStorage(
        bucket="test",
        endpoint_url="http://unused",
        access_key_id="test",
        secret_access_key="test",  # pragma: allowlist secret
        max_bytes=20,
        client=cast(BaseClient, fake),
    )
    tenant = uuid4()
    body = b"evidence"
    digest = __import__("hashlib").sha256(body).hexdigest()
    assert storage.put_if_absent(tenant, "raw/a", body, digest).sha256 == digest
    assert storage.put_if_absent(tenant, "raw/a", body, digest).length == len(body)
    assert storage.read(tenant, "raw/a") == body
    assert storage.head(tenant, "raw/a").sha256 == digest
    with pytest.raises(ValueError, match="byte limit"):
        storage.put_if_absent(
            tenant, "raw/large", b"x" * 21, __import__("hashlib").sha256(b"x" * 21).hexdigest()
        )
    with pytest.raises(ValueError, match="digest mismatch"):
        storage.put_if_absent(tenant, "raw/bad", body, "0" * 64)
    fake.objects[_object_key(tenant, "raw/a")] = (b"changed", {"sha256": "0" * 64})
    with pytest.raises(ValueError, match="different content"):
        storage.put_if_absent(tenant, "raw/a", body, digest)
    with pytest.raises(ValueError, match="stored object digest mismatch"):
        storage.read(tenant, "raw/a")
    fake.objects[_object_key(tenant, "raw/no-digest")] = (body, {})
    with pytest.raises(ValueError, match="no digest"):
        storage.head(tenant, "raw/no-digest")
    storage.delete(tenant, "raw/a")
