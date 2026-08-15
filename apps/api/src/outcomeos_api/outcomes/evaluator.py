from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from outcomeos_api.contracts.domain import canonical_document
from outcomeos_api.outcomes.state_machine import OutcomeState
from outcomeos_api.outcomes.templates import TEMPLATE_REGISTRY, TemplateStrategy

EVALUATOR_SCHEMA_VERSION = 1
MAX_WINDOW_SECONDS = 366 * 24 * 60 * 60
SUPPORTED_EVENT_SCHEMA_VERSION = 1


class Verdict(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class ReasonCode(StrEnum):
    AWAITING_REQUIRED_EVIDENCE = "awaiting_required_evidence"
    AWAITING_FINALIZATION = "awaiting_finalization"
    TEMPLATE_SATISFIED = "template_satisfied"
    REQUIRED_EVENT_MISSING = "required_event_missing"
    DISQUALIFYING_EVENT_PRESENT = "disqualifying_event_present"
    CONFLICTING_TERMINAL_EVENTS = "conflicting_terminal_events"
    AMBIGUOUS_ANCHOR_EVENT = "ambiguous_anchor_event"
    EVENT_OUTSIDE_EVALUATION_WINDOW = "event_outside_evaluation_window"
    NO_EFFECTIVE_CONTRACT = "no_effective_contract"
    AMBIGUOUS_EFFECTIVE_CONTRACT = "ambiguous_effective_contract"
    CONTRACT_NOT_EFFECTIVE = "contract_not_effective"
    RULE_NOT_PUBLISHED = "rule_not_published"
    CONTRACT_RULE_DIGEST_MISMATCH = "contract_rule_digest_mismatch"
    CROSS_TENANT_EVIDENCE = "cross_tenant_evidence"
    CANONICAL_EVENT_DIGEST_MISMATCH = "canonical_event_digest_mismatch"
    UNSUPPORTED_EVENT_SCHEMA = "unsupported_event_schema"
    SUBJECT_MISMATCH = "subject_mismatch"
    CURRENCY_MISMATCH = "currency_mismatch"
    UNSUPPORTED_TEMPLATE = "unsupported_template"
    INVALID_TIMESTAMP = "invalid_timestamp"
    INVALID_CONFIGURATION = "invalid_configuration"


class EvaluationError(ValueError):
    """Bounded fail-closed operational error; messages never contain supplied evidence."""

    def __init__(self, reason: ReasonCode):
        self.reason = reason
        super().__init__(reason.value)


def _aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


def _digest(value: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_document(value).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class MoneyMetadata:
    minor_units: int
    currency: str

    def __post_init__(self) -> None:
        if isinstance(self.minor_units, bool) or not isinstance(self.minor_units, int):
            raise EvaluationError(ReasonCode.INVALID_CONFIGURATION)
        if len(self.currency) != 3 or not self.currency.isalpha() or not self.currency.isupper():
            raise EvaluationError(ReasonCode.INVALID_CONFIGURATION)


@dataclass(frozen=True, slots=True)
class TrustedEvent:
    tenant_id: str
    event_id: str
    event_digest: str
    event_type: str
    schema_version: int
    occurred_at: datetime
    received_at: datetime
    subject_type: str
    subject_id: str
    references: tuple[tuple[str, str], ...] = ()
    money: MoneyMetadata | None = None
    status: str | None = None

    def __post_init__(self) -> None:
        if not _aware(self.occurred_at) or not _aware(self.received_at):
            raise EvaluationError(ReasonCode.INVALID_TIMESTAMP)
        if len(self.event_digest) != 64 or any(
            c not in "0123456789abcdef" for c in self.event_digest
        ):
            raise EvaluationError(ReasonCode.CANONICAL_EVENT_DIGEST_MISMATCH)
        if self.schema_version != SUPPORTED_EVENT_SCHEMA_VERSION:
            raise EvaluationError(ReasonCode.UNSUPPORTED_EVENT_SCHEMA)

    def canonical(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "event_id": self.event_id,
            "event_digest": self.event_digest,
            "event_type": self.event_type,
            "schema_version": self.schema_version,
            "occurred_at": self.occurred_at.astimezone(UTC).isoformat(),
            "received_at": self.received_at.astimezone(UTC).isoformat(),
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "references": sorted([list(item) for item in self.references]),
            "money": None
            if self.money is None
            else {"minor_units": self.money.minor_units, "currency": self.money.currency},
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class BoundEvaluationRequest:
    tenant_id: str
    outcome_id: str
    evaluation_id: str
    evaluator_schema_version: int
    as_of: datetime
    source_type: str
    source_id: str
    contract_version_id: str
    contract_digest: str
    rule_version_id: str
    rule_digest: str
    rule_published: bool
    template: str
    anchor_event_type: str
    evaluation_window_seconds: int
    finalization_window_seconds: int
    subject_type: str
    subject_id: str


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    event_id: str
    event_digest: str
    event_type: str
    role: str


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    outcome_id: str
    evaluation_id: str
    verdict: Verdict
    reason_code: ReasonCode
    progress_state: OutcomeState
    evidence: tuple[EvidenceReference, ...]
    input_digest: str
    decision_digest: str
    anchor_occurred_at: datetime
    finalization_boundary: datetime


def _validate_request(request: BoundEvaluationRequest) -> TemplateStrategy:
    if not _aware(request.as_of):
        raise EvaluationError(ReasonCode.INVALID_TIMESTAMP)
    if request.evaluator_schema_version != EVALUATOR_SCHEMA_VERSION:
        raise EvaluationError(ReasonCode.INVALID_CONFIGURATION)
    strategy = TEMPLATE_REGISTRY.get(request.template)
    if strategy is None:
        raise EvaluationError(ReasonCode.UNSUPPORTED_TEMPLATE)
    if request.anchor_event_type not in strategy.required:
        raise EvaluationError(ReasonCode.INVALID_CONFIGURATION)
    if not 0 < request.evaluation_window_seconds <= MAX_WINDOW_SECONDS:
        raise EvaluationError(ReasonCode.INVALID_CONFIGURATION)
    if not 0 <= request.finalization_window_seconds <= MAX_WINDOW_SECONDS:
        raise EvaluationError(ReasonCode.INVALID_CONFIGURATION)
    if not request.rule_published:
        raise EvaluationError(ReasonCode.RULE_NOT_PUBLISHED)
    for digest in (request.contract_digest, request.rule_digest):
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise EvaluationError(ReasonCode.CONTRACT_RULE_DIGEST_MISMATCH)
    return strategy


def evaluate(request: BoundEvaluationRequest, events: tuple[TrustedEvent, ...]) -> EvaluationResult:
    strategy = _validate_request(request)
    unique: dict[str, TrustedEvent] = {}
    for event in events:
        if event.tenant_id != request.tenant_id:
            raise EvaluationError(ReasonCode.CROSS_TENANT_EVIDENCE)
        if (event.subject_type, event.subject_id) != (request.subject_type, request.subject_id):
            raise EvaluationError(ReasonCode.SUBJECT_MISMATCH)
        prior = unique.get(event.event_id)
        if prior is not None and prior != event:
            raise EvaluationError(ReasonCode.CANONICAL_EVENT_DIGEST_MISMATCH)
        unique[event.event_id] = event
    ordered = tuple(
        sorted(unique.values(), key=lambda e: (e.occurred_at, e.event_type, e.event_id))
    )
    anchors = tuple(e for e in ordered if e.event_type == request.anchor_event_type)
    if len(anchors) != 1:
        raise EvaluationError(ReasonCode.AMBIGUOUS_ANCHOR_EVENT)
    anchor = anchors[0]
    evaluation_end = anchor.occurred_at + timedelta(seconds=request.evaluation_window_seconds)
    finalization = evaluation_end + timedelta(seconds=request.finalization_window_seconds)
    admissible = tuple(
        e
        for e in ordered
        if e is anchor
        or (
            anchor.occurred_at <= e.occurred_at < evaluation_end
            and e.received_at <= request.as_of
            and e.received_at <= finalization
        )
    )
    present = strategy.present_types(admissible)
    for conflict in strategy.conflicting:
        if conflict <= present:
            raise EvaluationError(ReasonCode.CONFLICTING_TERMINAL_EVENTS)
    currencies = {
        e.money.currency
        for e in admissible
        if e.event_type in strategy.monetary_events and e.money is not None
    }
    if len(currencies) > 1:
        raise EvaluationError(ReasonCode.CURRENCY_MISMATCH)
    if present & strategy.disqualifying:
        verdict, reason = Verdict.REJECTED, ReasonCode.DISQUALIFYING_EVENT_PRESENT
    elif not strategy.required <= present:
        if request.as_of < finalization:
            verdict, reason = Verdict.PENDING, ReasonCode.AWAITING_REQUIRED_EVIDENCE
        else:
            verdict, reason = Verdict.REJECTED, ReasonCode.REQUIRED_EVENT_MISSING
    elif request.as_of < finalization:
        verdict, reason = Verdict.PENDING, ReasonCode.AWAITING_FINALIZATION
    else:
        verdict, reason = Verdict.VERIFIED, ReasonCode.TEMPLATE_SATISFIED
    evidence = tuple(
        EvidenceReference(
            e.event_id,
            e.event_digest,
            e.event_type,
            "anchor"
            if e is anchor
            else "required"
            if e.event_type in strategy.required
            else "disqualifying",
        )
        for e in admissible
        if e.event_type in strategy.required | strategy.disqualifying
    )
    input_document = {
        "schema_version": request.evaluator_schema_version,
        "tenant_id": request.tenant_id,
        "as_of": request.as_of.astimezone(UTC).isoformat(),
        "source": [request.source_type, request.source_id],
        "contract": [request.contract_version_id, request.contract_digest],
        "rule": [request.rule_version_id, request.rule_digest],
        "template": request.template,
        "anchor_event_type": request.anchor_event_type,
        "evaluation_window_seconds": request.evaluation_window_seconds,
        "finalization_window_seconds": request.finalization_window_seconds,
        "subject": [request.subject_type, request.subject_id],
        "events": [e.canonical() for e in ordered],
    }
    input_digest = _digest(input_document)
    progress_state = (
        OutcomeState.VERIFIED
        if verdict is Verdict.VERIFIED
        else OutcomeState.REJECTED
        if verdict is Verdict.REJECTED
        else OutcomeState.CONVERTED
    )
    decision_document = {
        "outcome_id": request.outcome_id,
        "evaluation_id": request.evaluation_id,
        "input_digest": input_digest,
        "verdict": verdict.value,
        "reason_code": reason.value,
        "progress_state": progress_state.value,
        "evidence": [
            [item.event_id, item.event_digest, item.event_type, item.role] for item in evidence
        ],
        "finalization_boundary": finalization.astimezone(UTC).isoformat(),
    }
    return EvaluationResult(
        request.outcome_id,
        request.evaluation_id,
        verdict,
        reason,
        progress_state,
        evidence,
        input_digest,
        _digest(decision_document),
        anchor.occurred_at,
        finalization,
    )
