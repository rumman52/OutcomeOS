from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from outcomeos_api.common import Money, WorkspaceRegion, currency_exponent
from outcomeos_api.domain import DomainError
from outcomeos_api.events import CanonicalEvent, ConsentFlags
from outcomeos_api.outcomes.state_machine import (
    ALLOWED_TRANSITIONS,
    OutcomeState,
    transition_outcome,
)


def test_currency_exponents_and_exact_decimal_strings() -> None:
    assert Money(12345, "USD").decimal_string() == "123.45"
    assert Money(12345, "JPY").decimal_string() == "12345"
    assert Money(12345, "BHD").decimal_string() == "12.345"
    assert currency_exponent("USD") == 2


def test_different_currencies_cannot_be_combined() -> None:
    with pytest.raises(DomainError, match="different currencies"):
        Money(100, "USD").add(Money(100, "JPY"))


def test_global_workspace_regions() -> None:
    us = WorkspaceRegion("us", "en-US", "America/New_York", "usd")
    gb = WorkspaceRegion("GB", "en-GB", "Europe/London", "GBP")
    assert (us.country, us.default_currency) == ("US", "USD")
    assert gb.timezone == "Europe/London"


def test_canonical_event_requires_aware_timestamps() -> None:
    base = {
        "event_id": uuid4(),
        "tenant_id": uuid4(),
        "provider": "generic_webhook",
        "source_type": "commerce",
        "payload_digest": "a" * 64,
        "event_type": "order.created",
        "occurred_at": datetime.now(UTC),
        "received_at": datetime.now(UTC),
        "subject_type": "order",
        "subject_id": "ord_1",
        "consent": ConsentFlags(processing_permitted=True, purpose="fulfil contract"),
        "payload": {"status": "created"},
    }
    event = CanonicalEvent.model_validate(base)
    assert event.schema_version == 1
    with pytest.raises(ValidationError, match="UTC offset"):
        CanonicalEvent.model_validate({**base, "occurred_at": datetime(2026, 8, 8)})


def test_every_allowed_outcome_transition_and_audit_shape() -> None:
    for source, targets in ALLOWED_TRANSITIONS.items():
        for target in targets:
            transition = transition_outcome(
                current_state=source,
                expected_version=4,
                next_state=target,
                tenant_id="tenant-a",
                outcome_id="outcome-1",
                reason_code="evidence.accepted",
                explanation="Required evidence was accepted.",
                actor_id="system:evaluator",
                source_event_ids=("event-1",),
                evidence_ids=("evidence-1",),
                rule_version_id="rule-v1",
                contract_version_id="contract-v1",
                idempotency_key=f"{source}:{target}",
                now=datetime(2026, 8, 8, tzinfo=UTC),
            )
            assert transition.version == 5
            assert transition.to_state is target


def test_every_forbidden_outcome_transition_fails() -> None:
    for source in OutcomeState:
        for target in OutcomeState:
            if target in ALLOWED_TRANSITIONS[source]:
                continue
            with pytest.raises(DomainError, match="not allowed"):
                transition_outcome(
                    current_state=source,
                    expected_version=0,
                    next_state=target,
                    tenant_id="tenant-a",
                    outcome_id="outcome-1",
                    reason_code="invalid",
                    explanation="Invalid transition test.",
                    actor_id="system:test",
                    source_event_ids=(),
                    evidence_ids=(),
                    rule_version_id="rule-v1",
                    contract_version_id=None,
                    idempotency_key=f"{source}:{target}",
                )
