from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from itertools import permutations
from typing import Any

import pytest

from outcomeos_api.outcomes.evaluator import (
    BoundEvaluationRequest,
    EvaluationError,
    MoneyMetadata,
    ReasonCode,
    TrustedEvent,
    Verdict,
    evaluate,
)
from outcomeos_api.outcomes.state_machine import OutcomeState, transition_outcome

NOW = datetime(2026, 8, 15, tzinfo=UTC)
DIGEST = "a" * 64


def event(kind: str, *, seconds: int = 0, event_id: str | None = None) -> TrustedEvent:
    return TrustedEvent(
        tenant_id="tenant-a",
        event_id=event_id or kind,
        event_digest=DIGEST,
        event_type=kind,
        schema_version=1,
        occurred_at=NOW + timedelta(seconds=seconds),
        received_at=NOW + timedelta(seconds=seconds),
        subject_type="order",
        subject_id="subject-1",
    )


def request(template: str, anchor: str) -> BoundEvaluationRequest:
    return BoundEvaluationRequest(
        tenant_id="tenant-a",
        outcome_id="outcome-1",
        evaluation_id="evaluation-1",
        evaluator_schema_version=1,
        as_of=NOW + timedelta(seconds=20),
        source_type="endpoint",
        source_id="source-1",
        contract_version_id="contract-version-1",
        contract_digest="b" * 64,
        rule_version_id="rule-version-1",
        rule_digest="c" * 64,
        rule_published=True,
        template=template,
        anchor_event_type=anchor,
        evaluation_window_seconds=10,
        finalization_window_seconds=5,
        subject_type="order",
        subject_id="subject-1",
    )


@pytest.mark.parametrize(
    ("template", "anchor", "types"),
    [
        (
            "delivered_paid_order",
            "order.confirmed",
            ("order.confirmed", "fulfillment.delivered", "payment.succeeded"),
        ),
        ("attended_booking", "booking.created", ("booking.created", "booking.attended")),
        (
            "qualified_lead_accepted",
            "lead.captured",
            ("lead.captured", "lead.qualified", "lead.accepted"),
        ),
        (
            "paid_activated_subscription",
            "account.activated",
            ("account.activated", "payment.succeeded"),
        ),
    ],
)
def test_all_templates_verify(template: str, anchor: str, types: tuple[str, ...]) -> None:
    result = evaluate(
        request(template, anchor), tuple(event(kind, seconds=i) for i, kind in enumerate(types))
    )
    assert result.verdict is Verdict.VERIFIED
    assert result.reason_code is ReasonCode.TEMPLATE_SATISFIED
    assert result.progress_state is OutcomeState.VERIFIED


def test_missing_evidence_is_pending_then_rejected() -> None:
    req = request("qualified_lead_accepted", "lead.captured")
    evidence = (event("lead.captured"), event("lead.qualified", seconds=1))
    assert (
        evaluate(replace(req, as_of=NOW + timedelta(seconds=14)), evidence).verdict
        is Verdict.PENDING
    )
    result = evaluate(req, evidence)
    assert (result.verdict, result.reason_code) == (
        Verdict.REJECTED,
        ReasonCode.REQUIRED_EVENT_MISSING,
    )


@pytest.mark.parametrize(
    ("template", "anchor", "required", "bad"),
    [
        (
            "delivered_paid_order",
            "order.confirmed",
            ("fulfillment.delivered", "payment.succeeded"),
            "order.returned",
        ),
        (
            "paid_activated_subscription",
            "account.activated",
            ("payment.succeeded",),
            "payment.refunded",
        ),
    ],
)
def test_disqualifiers_reject(
    template: str, anchor: str, required: tuple[str, ...], bad: str
) -> None:
    evidence = (
        event(anchor),
        *(event(kind, seconds=i + 1) for i, kind in enumerate(required)),
        event(bad, seconds=5),
    )
    assert (
        evaluate(request(template, anchor), evidence).reason_code
        is ReasonCode.DISQUALIFYING_EVENT_PRESENT
    )


def test_booking_conflicting_terminal_evidence_fails_closed() -> None:
    with pytest.raises(EvaluationError, match="conflicting_terminal_events"):
        evaluate(
            request("attended_booking", "booking.created"),
            (
                event("booking.created"),
                event("booking.attended", seconds=1),
                event("booking.no_show", seconds=2),
            ),
        )


def test_half_open_window_and_finalization_boundary() -> None:
    req = request("attended_booking", "booking.created")
    outside = (event("booking.created"), event("booking.attended", seconds=10))
    assert evaluate(req, outside).reason_code is ReasonCode.REQUIRED_EVENT_MISSING
    inside = (event("booking.created"), event("booking.attended", seconds=9))
    assert (
        evaluate(replace(req, as_of=NOW + timedelta(seconds=14)), inside).reason_code
        is ReasonCode.AWAITING_FINALIZATION
    )
    assert (
        evaluate(replace(req, as_of=NOW + timedelta(seconds=15)), inside).verdict
        is Verdict.VERIFIED
    )


def test_ordering_and_exact_duplicates_do_not_change_digests() -> None:
    req = request("delivered_paid_order", "order.confirmed")
    evidence = (
        event("order.confirmed"),
        event("fulfillment.delivered", seconds=1),
        event("payment.succeeded", seconds=2),
    )
    results = [evaluate(req, tuple(order)) for order in permutations(evidence)]
    assert len({item.input_digest for item in results}) == 1
    assert len({item.decision_digest for item in results}) == 1
    assert evaluate(req, evidence + (evidence[-1],)).decision_digest == results[0].decision_digest


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ({"tenant_id": "tenant-b"}, ReasonCode.CROSS_TENANT_EVIDENCE),
        ({"subject_id": "other"}, ReasonCode.SUBJECT_MISMATCH),
        ({"schema_version": 2}, ReasonCode.UNSUPPORTED_EVENT_SCHEMA),
    ],
)
def test_evidence_validation_fails_closed(mutation: dict[str, Any], reason: ReasonCode) -> None:
    with pytest.raises(EvaluationError) as caught:
        evaluate(
            request("attended_booking", "booking.created"),
            (replace(event("booking.created"), **mutation),),
        )
    assert caught.value.reason is reason


def test_conflicting_duplicate_id_fails_closed() -> None:
    first = event("booking.created", event_id="same")
    second = event("booking.attended", event_id="same")
    with pytest.raises(EvaluationError, match="canonical_event_digest_mismatch"):
        evaluate(request("attended_booking", "booking.created"), (first, second))


def test_naive_timestamps_and_unpublished_or_bad_digest_fail_closed() -> None:
    with pytest.raises(EvaluationError, match="invalid_timestamp"):
        replace(event("booking.created"), occurred_at=NOW.replace(tzinfo=None))
    req = request("attended_booking", "booking.created")
    with pytest.raises(EvaluationError, match="rule_not_published"):
        evaluate(replace(req, rule_published=False), (event("booking.created"),))
    with pytest.raises(EvaluationError, match="contract_rule_digest_mismatch"):
        evaluate(replace(req, contract_digest="bad"), (event("booking.created"),))


def test_money_currency_must_be_consistent_without_calculation() -> None:
    req = request("delivered_paid_order", "order.confirmed")
    evidence = (
        replace(event("order.confirmed"), money=MoneyMetadata(1000, "USD")),
        event("fulfillment.delivered", seconds=1),
        replace(event("payment.succeeded", seconds=2), money=MoneyMetadata(1000, "EUR")),
    )
    with pytest.raises(EvaluationError, match="currency_mismatch"):
        evaluate(req, evidence)
    result = evaluate(
        req, (evidence[0], evidence[1], replace(evidence[2], money=MoneyMetadata(1000, "USD")))
    )
    assert result.verdict is Verdict.VERIFIED


def test_state_machine_allows_only_factual_rejection_from_converted() -> None:
    transition = transition_outcome(
        current_state=OutcomeState.CONVERTED,
        expected_version=2,
        next_state=OutcomeState.REJECTED,
        tenant_id="tenant-a",
        outcome_id="outcome-1",
        reason_code="required_event_missing",
        explanation="bounded deterministic result",
        actor_id="worker",
        source_event_ids=("event-1",),
        evidence_ids=("event-1",),
        rule_version_id="rule-1",
        contract_version_id="contract-1",
        idempotency_key="job-1",
        now=NOW,
    )
    assert (transition.to_state, transition.occurred_at, transition.version) == (
        OutcomeState.REJECTED,
        NOW,
        3,
    )
