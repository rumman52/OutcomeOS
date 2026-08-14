from datetime import UTC, datetime
from uuid import uuid4
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from outcomeos_api.config import Settings
from outcomeos_api.events.schemas import PublicEventInput
from outcomeos_api.ingestion.signatures import SignatureError, authenticate, sign
from outcomeos_api.integrations.endpoints import create_endpoint_material
from outcomeos_api.integrations.repositories import EndpointRepository
from outcomeos_api.integrations.secrets import SecretCipher


def test_exact_raw_byte_signatures_and_replay_window() -> None:
    secret = b"signing-secret"
    timestamp = b"1786665600"
    body = b'{"b":2, "a":1}'
    signature = f"v1={sign(secret, timestamp, body)}"
    now = datetime.fromtimestamp(int(timestamp), UTC)
    authenticate(
        secrets=[secret],
        timestamp_header=timestamp,
        signature_headers=[signature],
        body=body,
        replay_window_seconds=300,
        now=now,
    )
    for changed in (b'{"a":1,"b":2}', body + b" ", body[:-1] + b"2"):
        with pytest.raises(SignatureError):
            authenticate(
                secrets=[secret],
                timestamp_header=timestamp,
                signature_headers=[signature],
                body=changed,
                replay_window_seconds=300,
                now=now,
            )
    with pytest.raises(SignatureError):
        authenticate(
            secrets=[secret],
            timestamp_header=timestamp,
            signature_headers=[signature],
            body=body,
            replay_window_seconds=300,
            now=datetime.fromtimestamp(int(timestamp) + 301, UTC),
        )


def test_malformed_and_duplicate_signature_headers_fail_closed() -> None:
    for headers in ([], ["v2=" + "0" * 64], ["v1=" + "A" * 64], ["v1=" + "0" * 64] * 2):
        with pytest.raises(SignatureError):
            authenticate(
                secrets=[b"x"],
                timestamp_header=b"1",
                signature_headers=headers,
                body=b"{}",
                replay_window_seconds=1,
                now=datetime.fromtimestamp(1, UTC),
            )


def test_public_input_is_strict_and_consent_is_explicit() -> None:
    valid = {
        "provider_event_id": "evt_1",
        "event_type": "order.created",
        "occurred_at": "2026-08-14T00:00:00Z",
        "subject_type": "order",
        "subject_id": "ord_1",
        "consent": {"processing_permitted": True, "purpose": "order"},
        "payload": {"answer": 42},
    }
    assert PublicEventInput.model_validate(valid).provider_event_id == "evt_1"
    for update in (
        {"tenant_id": str(uuid4())},
        {"consent": {"processing_permitted": False, "purpose": "order"}},
        {"occurred_at": "2026-08-14T00:00:00"},
    ):
        with pytest.raises(ValidationError):
            PublicEventInput.model_validate(valid | update)


def test_endpoint_material_only_persists_digest_and_ciphertext() -> None:
    tenant_id = uuid4()
    cipher = SecretCipher({"current": b"k" * 32}, "current")
    material = create_endpoint_material(
        tenant_id=tenant_id,
        cipher=cipher,
        token_bytes=32,
        secret_lifetime_seconds=3600,
        now=datetime(2026, 8, 14, tzinfo=UTC),
    )
    assert len(material.public_token_digest) == 32
    assert material.signing_secret.encode() not in material.encrypted_secret.ciphertext
    assert (
        cipher.decrypt(
            material.encrypted_secret, tenant_id=tenant_id, endpoint_id=material.id, version=1
        )
        == material.signing_secret.encode()
    )


def test_keyring_parsing_fails_closed() -> None:
    with pytest.raises(ValueError):
        Settings(
            integration_keyring="bad", integration_active_key_id="current"
        ).parsed_integration_keyring()


def test_endpoint_repository_always_passes_tenant_scope() -> None:
    session = MagicMock()
    result = session.execute.return_value
    result.mappings.return_value.all.return_value = []
    result.mappings.return_value.one_or_none.return_value = None
    result.rowcount = 1
    tenant_id, endpoint_id = uuid4(), uuid4()
    repository = EndpointRepository(session, tenant_id)
    assert repository.list() == []
    assert repository.get(endpoint_id) is None
    repository.insert(
        {"tenant_id": tenant_id},
        {"tenant_id": tenant_id},
    )
    assert repository.disable(endpoint_id, revoked=False, now=datetime.now(UTC))
    assert repository.disable(endpoint_id, revoked=True, now=datetime.now(UTC))
    assert repository.lock_latest_version(endpoint_id) is None
    for call in session.execute.call_args_list:
        if len(call.args) > 1:
            assert call.args[1]["tenant_id"] == tenant_id
