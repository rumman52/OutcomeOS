from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterable

from outcomeos_api.models import Money, OutcomeStage


class InvalidTransition(ValueError):
    pass


TRANSITIONS = {
    OutcomeStage.CAPTURED: {OutcomeStage.QUALIFIED, OutcomeStage.DISQUALIFIED},
    OutcomeStage.QUALIFIED: {OutcomeStage.CONVERTED, OutcomeStage.DISQUALIFIED},
    OutcomeStage.CONVERTED: {OutcomeStage.VERIFIED, OutcomeStage.DISQUALIFIED},
    OutcomeStage.VERIFIED: set(),
    OutcomeStage.DISQUALIFIED: set(),
}


def transition(current: OutcomeStage, target: OutcomeStage) -> OutcomeStage:
    if target not in TRANSITIONS[current]:
        raise InvalidTransition(f"invalid outcome transition: {current} -> {target}")
    return target


@dataclass(frozen=True)
class ProfitInputs:
    revenue: Money
    product_cost: Money | None
    delivery_cost: Money | None
    campaign_spend: Money | None
    estimated_fields: tuple[str, ...] = ()


def contribution_profit(values: ProfitInputs) -> tuple[Money | None, list[str]]:
    amounts = [values.product_cost, values.delivery_cost, values.campaign_spend]
    missing = [
        name
        for name, value in zip(
            ("product_cost", "delivery_cost", "campaign_spend"), amounts, strict=True
        )
        if value is None
    ]
    currencies = {m.currency for m in [values.revenue, *[a for a in amounts if a]]}
    if len(currencies) != 1:
        raise ValueError("all source amounts must use the same currency")
    if missing:
        return None, missing
    exact = values.revenue.minor - sum(a.minor for a in amounts if a is not None)
    annotations = [f"estimated:{name}" for name in values.estimated_fields]
    return Money(minor=exact, currency=values.revenue.currency), annotations


def prohibit_float(values: Iterable[object]) -> None:
    if any(isinstance(value, float) for value in values):
        raise TypeError("floating-point values are prohibited in financial calculations")


def utcnow() -> datetime:
    return datetime.now(UTC)
