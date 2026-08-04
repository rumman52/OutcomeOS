import time
from uuid import UUID, uuid4

import pytest

from outcomeos_api.tenancy import (
    JobTenantContext,
    cache_key,
    object_key,
    sign_job_context,
    verify_job_context,
)


def test_tenant_namespaces_and_signed_job_context(tenant_ids):
    tenant_id = UUID(tenant_ids["tenant_a"])
    assert object_key(tenant_id, "evidence", "item.pdf").startswith(f"tenants/{tenant_id}/")
    assert cache_key(tenant_id, "contact", "42") == f"tenant:{tenant_id}:contact:42"
    context = JobTenantContext(tenant_id, uuid4(), int(time.time()) + 60)
    token = sign_job_context(context, b"test-secret")
    assert verify_job_context(token, b"test-secret") == context
    with pytest.raises(ValueError):
        verify_job_context(token, b"wrong-secret")


def test_object_key_rejects_traversal(tenant_ids):
    with pytest.raises(ValueError):
        object_key(UUID(tenant_ids["tenant_a"]), "../other-tenant/secret")
