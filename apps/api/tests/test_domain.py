import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from outcomeos_api.domain import (
    Actor,
    DomainError,
    Role,
    Store,
    attribute,
    negotiate_contract,
    verify_webhook,
)


@pytest.fixture
def store() -> Store:
    return Store()


@pytest.fixture
def admin() -> Actor:
    return Actor("tenant-a", "alice", Role.ADMIN)


def order_data(order_id: str = "o-1") -> dict[str, object]:
    return {"id": order_id, "customer_id": "c-1", "total": "12.50", "currency": "usd"}


def test_tenant_isolation_and_rbac(store: Store, admin: Actor) -> None:
    store.create_order(admin, order_data())
    with pytest.raises(DomainError, match="not found"):
        store.get_order(Actor("tenant-b", "bob", Role.ADMIN), "o-1")
    with pytest.raises(PermissionError):
        store.create_order(Actor("tenant-a", "vic", Role.VIEWER), order_data("o-2"))


def test_webhook_signature_and_replay_window() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    timestamp = int(now.timestamp())
    body = b'{"id":"evt-1"}'
    signature = hmac.new(b"secret", f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    assert verify_webhook("secret", body, signature, timestamp, now)
    assert not verify_webhook("secret", body + b"x", signature, timestamp, now)
    assert not verify_webhook("secret", body, signature, timestamp, now + timedelta(minutes=6))


def test_canonical_event_idempotency_is_tenant_scoped(store: Store) -> None:
    assert store.ingest_event("a", "", {"b": 2, "a": 1})
    assert not store.ingest_event("a", "", {"a": 1, "b": 2})
    assert store.ingest_event("b", "", {"a": 1, "b": 2})


def test_transactional_outbox_written_with_aggregate(store: Store, admin: Actor) -> None:
    store.create_order(admin, order_data())
    assert [(m.topic, m.aggregate_id) for m in store.outbox] == [("order.created", "o-1")]
    with pytest.raises(DomainError):
        store.create_order(admin, order_data())
    assert len(store.outbox) == 1


def test_attribution_boundary_and_deterministic_tie_break() -> None:
    conversion = datetime(2026, 2, 1, tzinfo=UTC)
    touches = [
        {"id": "old", "at": conversion - timedelta(days=30, seconds=1)},
        {"id": "a", "at": conversion - timedelta(days=30)},
        {"id": "b", "at": conversion - timedelta(days=30)},
        {"id": "future", "at": conversion + timedelta(seconds=1)},
    ]
    winner = attribute(touches, conversion)
    assert winner is not None
    assert winner["id"] == "b"


@pytest.mark.parametrize(
    "patch", [{}, {"id": "x", "customer_id": "c", "total": 0, "currency": "USD"}]
)
def test_order_validation(store: Store, admin: Actor, patch: dict[str, object]) -> None:
    with pytest.raises(DomainError):
        store.create_order(admin, patch)


def test_transition_authorization_state_machine_and_optimistic_concurrency(
    store: Store, admin: Actor
) -> None:
    store.create_order(admin, order_data())
    with pytest.raises(PermissionError):
        store.transition(Actor("tenant-a", "v", Role.VIEWER), "o-1", "confirmed", 0)
    confirmed = store.transition(admin, "o-1", "confirmed", 0)
    assert confirmed.version == 1
    with pytest.raises(DomainError, match="concurrent"):
        store.transition(admin, "o-1", "fulfilled", 0)
    with pytest.raises(DomainError, match="invalid"):
        store.transition(admin, "o-1", "cancelled", 1)


def test_contract_versioning() -> None:
    assert negotiate_contract("2026-01") == "2026-01"
    with pytest.raises(DomainError, match="unsupported"):
        negotiate_contract("latest")


def test_ledger_credits_are_append_only_and_idempotent(store: Store, admin: Actor) -> None:
    store.credit(admin, "wallet", Decimal("5"), "ref-1")
    snapshot = list(store.ledger)
    with pytest.raises(DomainError):
        store.credit(admin, "wallet", Decimal("5"), "ref-1")
    assert store.ledger == snapshot
    with pytest.raises(PermissionError):
        store.credit(Actor("tenant-a", "agent", Role.AGENT), "wallet", Decimal("5"), "r2")


def test_dispute_resolution_is_authorized_tenant_scoped_and_final(
    store: Store, admin: Actor
) -> None:
    store.resolve_dispute(admin, "d-1", "upheld")
    store.resolve_dispute(Actor("tenant-b", "b", Role.ADMIN), "d-1", "reversed")
    with pytest.raises(DomainError, match="already"):
        store.resolve_dispute(admin, "d-1", "reversed")
    with pytest.raises(PermissionError):
        store.resolve_dispute(Actor("tenant-a", "x", Role.AGENT), "d-2", "upheld")
