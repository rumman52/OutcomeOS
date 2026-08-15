from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from outcomeos_api.domain import DomainError


class OutcomeState(StrEnum):
    CAPTURED = "captured"
    QUALIFIED = "qualified"
    CONVERTED = "converted"
    VERIFIED = "verified"
    BILLABLE = "billable"
    DISPUTED = "disputed"
    REJECTED = "rejected"
    FAILED = "failed"
    SETTLED = "settled"
    CREDITED = "credited"


ALLOWED_TRANSITIONS: dict[OutcomeState, frozenset[OutcomeState]] = {
    OutcomeState.CAPTURED: frozenset({OutcomeState.QUALIFIED, OutcomeState.REJECTED}),
    OutcomeState.QUALIFIED: frozenset({OutcomeState.CONVERTED, OutcomeState.REJECTED}),
    OutcomeState.CONVERTED: frozenset(
        {OutcomeState.VERIFIED, OutcomeState.REJECTED, OutcomeState.FAILED}
    ),
    OutcomeState.VERIFIED: frozenset({OutcomeState.BILLABLE}),
    OutcomeState.BILLABLE: frozenset({OutcomeState.SETTLED, OutcomeState.DISPUTED}),
    OutcomeState.DISPUTED: frozenset({OutcomeState.SETTLED, OutcomeState.CREDITED}),
    OutcomeState.REJECTED: frozenset(),
    OutcomeState.FAILED: frozenset(),
    OutcomeState.SETTLED: frozenset(),
    OutcomeState.CREDITED: frozenset(),
}


@dataclass(frozen=True, slots=True)
class OutcomeTransition:
    tenant_id: str
    outcome_id: str
    from_state: OutcomeState
    to_state: OutcomeState
    reason_code: str
    explanation: str
    actor_id: str
    source_event_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    rule_version_id: str
    contract_version_id: str | None
    idempotency_key: str
    occurred_at: datetime
    version: int


def transition_outcome(
    *,
    current_state: OutcomeState,
    expected_version: int,
    next_state: OutcomeState,
    tenant_id: str,
    outcome_id: str,
    reason_code: str,
    explanation: str,
    actor_id: str,
    source_event_ids: tuple[str, ...],
    evidence_ids: tuple[str, ...],
    rule_version_id: str,
    contract_version_id: str | None,
    idempotency_key: str,
    now: datetime | None = None,
) -> OutcomeTransition:
    if next_state not in ALLOWED_TRANSITIONS[current_state]:
        raise DomainError(f"transition {current_state} -> {next_state} is not allowed")
    required = (
        tenant_id,
        outcome_id,
        reason_code,
        explanation,
        actor_id,
        rule_version_id,
        idempotency_key,
    )
    if any(not value.strip() for value in required):
        raise DomainError("transition audit fields must not be blank")
    if expected_version < 0:
        raise DomainError("optimistic-concurrency version must not be negative")
    return OutcomeTransition(
        tenant_id,
        outcome_id,
        current_state,
        next_state,
        reason_code,
        explanation,
        actor_id,
        source_event_ids,
        evidence_ids,
        rule_version_id,
        contract_version_id,
        idempotency_key,
        now or datetime.now(UTC),
        expected_version + 1,
    )
