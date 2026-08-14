import hashlib
import os
from uuid import uuid4

import boto3
import pytest
from botocore.exceptions import ClientError

from outcomeos_api.storage import ObjectHead, S3ObjectStorage

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def storage() -> S3ObjectStorage:
    endpoint = os.getenv("INTEGRATION_S3_ENDPOINT_URL")
    access = os.getenv("INTEGRATION_S3_ACCESS_KEY_ID")
    secret = os.getenv("INTEGRATION_S3_SECRET_ACCESS_KEY")
    bucket = os.getenv("INTEGRATION_S3_BUCKET")
    if endpoint is None or access is None or secret is None or bucket is None:
        pytest.fail(
            "all INTEGRATION_S3_* settings are required for the S3 integration suite", pytrace=False
        )
    client = boto3.client(
        "s3", endpoint_url=endpoint, aws_access_key_id=access, aws_secret_access_key=secret
    )
    try:
        client.create_bucket(Bucket=bucket)
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") not in {
            "BucketAlreadyOwnedByYou",
            "BucketAlreadyExists",
        }:
            raise
    return S3ObjectStorage(
        bucket=bucket,
        endpoint_url=endpoint,
        access_key_id=access,
        secret_access_key=secret,
        max_bytes=1024,
        client=client,
    )


def test_real_s3_conditional_put_read_head_delete_and_tenant_separation(
    storage: S3ObjectStorage,
) -> None:
    tenant_a, tenant_b = uuid4(), uuid4()
    body = b"immutable evidence"
    digest = hashlib.sha256(body).hexdigest()
    assert storage.put_if_absent(tenant_a, "raw/receipt", body, digest) == ObjectHead(
        len(body), digest
    )
    assert storage.put_if_absent(tenant_a, "raw/receipt", body, digest) == ObjectHead(
        len(body), digest
    )
    assert storage.read(tenant_a, "raw/receipt") == body
    assert storage.head(tenant_a, "raw/receipt") == ObjectHead(len(body), digest)
    with pytest.raises(ClientError):
        storage.read(tenant_b, "raw/receipt")
    with pytest.raises(ValueError, match="digest mismatch"):
        storage.put_if_absent(tenant_a, "raw/bad", body, "0" * 64)
    storage.delete(tenant_a, "raw/receipt")
    with pytest.raises(ClientError):
        storage.head(tenant_a, "raw/receipt")
