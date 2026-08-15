from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from outcomeos_api.domain import DomainError

SUPPORTED_CURRENCIES = frozenset(
    {"AED", "AUD", "BDT", "CAD", "CHF", "EUR", "GBP", "INR", "JPY", "SAR", "SGD", "USD"}
)


def canonical_document(value: Mapping[str, Any]) -> str:
    try:
        return json.dumps(
            dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        )
    except (TypeError, ValueError) as exc:
        raise DomainError("document must contain bounded JSON values") from exc


def document_digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_document(value).encode()).hexdigest()


def validate_currency(value: str) -> str:
    currency = value.upper()
    if currency not in SUPPORTED_CURRENCIES:
        raise DomainError("unsupported ISO 4217 currency")
    return currency


def validate_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise DomainError("timezone must be an IANA timezone") from exc
    return value


def _integer(value: object, message: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise DomainError(message)
    return value


@dataclass(frozen=True, slots=True)
class FixedFee:
    amount_minor: int
    currency: str

    def __post_init__(self) -> None:
        amount = _integer(self.amount_minor, "fixed fee must be an integer")
        if amount <= 0:
            raise DomainError("fixed fee must be positive")
        object.__setattr__(self, "currency", validate_currency(self.currency))


@dataclass(frozen=True, slots=True)
class BasisPoints:
    rate: int
    currency: str
    floor_minor: int | None = None
    cap_minor: int | None = None

    def __post_init__(self) -> None:
        rate = _integer(self.rate, "basis points must be an integer")
        if not 1 <= rate <= 10_000:
            raise DomainError("basis points must be between 1 and 10000")
        for value in (self.floor_minor, self.cap_minor):
            if value is not None and _integer(value, "floor and cap must be integers") < 0:
                raise DomainError("floor and cap must be non-negative")
        if (
            self.floor_minor is not None
            and self.cap_minor is not None
            and self.floor_minor > self.cap_minor
        ):
            raise DomainError("floor cannot exceed cap")
        object.__setattr__(self, "currency", validate_currency(self.currency))


class RuleState(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    RETIRED = "retired"


RULE_TEMPLATES = frozenset(
    {
        "delivered_paid_order",
        "attended_booking",
        "qualified_lead_accepted",
        "paid_activated_subscription",
    }
)
ALLOWED_RULE_KEYS = frozenset(
    {"required_event_types", "required_statuses", "max_age_seconds", "schema_version"}
)


@dataclass(frozen=True, slots=True)
class RuleVersion:
    id: str
    version: int
    template: str
    definition: Mapping[str, Any]
    state: RuleState = RuleState.DRAFT
    digest: str | None = None

    def __post_init__(self) -> None:
        if self.version < 1 or self.template not in RULE_TEMPLATES:
            raise DomainError("invalid rule version or template")
        if not set(self.definition).issubset(ALLOWED_RULE_KEYS):
            raise DomainError("rule definition contains unsupported fields")
        encoded = canonical_document(self.definition)
        if len(encoded.encode()) > 16_384:
            raise DomainError("rule definition is too large")
        object.__setattr__(self, "definition", MappingProxyType(dict(self.definition)))

    def publish(self) -> RuleVersion:
        if self.state is not RuleState.DRAFT:
            raise DomainError("only a draft rule can be published")
        return replace(self, state=RuleState.PUBLISHED, digest=document_digest(self.definition))

    def retire(self) -> RuleVersion:
        if self.state is not RuleState.PUBLISHED:
            raise DomainError("only a published rule can be retired")
        return replace(self, state=RuleState.RETIRED)


class ContractState(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"


class VersionState(StrEnum):
    DRAFT = "draft"
    PROPOSED = "proposed"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    WITHDRAWN = "withdrawn"


@dataclass(frozen=True, slots=True)
class Acceptance:
    version_id: str
    digest: str
    party_role: str
    principal_id: str
    accepted_at: datetime


@dataclass(frozen=True, slots=True)
class ContractVersion:
    id: str
    version: int
    terms: Mapping[str, Any]
    required_roles: frozenset[str]
    effective_start: datetime
    effective_end: datetime | None = None
    state: VersionState = VersionState.DRAFT
    digest: str | None = None
    acceptances: tuple[Acceptance, ...] = ()

    def __post_init__(self) -> None:
        if self.version < 1 or not self.required_roles:
            raise DomainError("version and required party roles are required")
        if self.effective_start.tzinfo is None or (
            self.effective_end and self.effective_end.tzinfo is None
        ):
            raise DomainError("effective timestamps must be timezone-aware")
        if self.effective_end is not None and self.effective_start >= self.effective_end:
            raise DomainError("effective end must follow start")
        object.__setattr__(self, "terms", MappingProxyType(dict(self.terms)))

    def propose(self) -> ContractVersion:
        if self.state is not VersionState.DRAFT:
            raise DomainError("only a draft version can be proposed")
        return replace(self, state=VersionState.PROPOSED, digest=document_digest(self.terms))

    def accept(
        self, role: str, principal_id: str, accepted_at: datetime, digest: str
    ) -> ContractVersion:
        if (
            self.state is not VersionState.PROPOSED
            or digest != self.digest
            or role not in self.required_roles
        ):
            raise DomainError("acceptance must match the proposed digest and a required role")
        if accepted_at.tzinfo is None:
            raise DomainError("acceptance timestamp must be timezone-aware")
        remaining = tuple(a for a in self.acceptances if a.party_role != role)
        return replace(
            self,
            acceptances=remaining + (Acceptance(self.id, digest, role, principal_id, accepted_at),),
        )

    def activate(self) -> ContractVersion:
        accepted = {a.party_role for a in self.acceptances if a.digest == self.digest}
        if self.state is not VersionState.PROPOSED or accepted != set(self.required_roles):
            raise DomainError("all required parties must accept the exact digest")
        return replace(self, state=VersionState.ACTIVE)


@dataclass(frozen=True, slots=True)
class EffectiveCandidate:
    version: ContractVersion
    source_type: str
    source_id: str


@dataclass(frozen=True, slots=True)
class Selection:
    version: ContractVersion | None
    reason: str | None


def select_effective_contract(
    candidates: Sequence[EffectiveCandidate],
    source_type: str,
    source_id: str,
    occurred_at: datetime,
) -> Selection:
    if occurred_at.tzinfo is None:
        raise DomainError("occurred_at must be timezone-aware")
    matches = sorted(
        (
            item.version
            for item in candidates
            if item.source_type == source_type
            and item.source_id == source_id
            and item.version.state is VersionState.ACTIVE
            and item.version.effective_start <= occurred_at
            and (item.version.effective_end is None or occurred_at < item.version.effective_end)
        ),
        key=lambda item: item.id,
    )
    if not matches:
        return Selection(None, "no_effective_contract")
    if len(matches) != 1:
        return Selection(None, "ambiguous_effective_contract")
    return Selection(matches[0], None)
