from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TemplateStrategy:
    name: str
    required: frozenset[str]
    disqualifying: frozenset[str]
    conflicting: tuple[frozenset[str], ...] = ()
    monetary_events: frozenset[str] = frozenset()

    def present_types(self, events: Sequence[Any]) -> frozenset[str]:
        return frozenset(str(event.event_type) for event in events)


TEMPLATE_REGISTRY: dict[str, TemplateStrategy] = {
    item.name: item
    for item in (
        TemplateStrategy(
            "delivered_paid_order",
            frozenset({"order.confirmed", "fulfillment.delivered", "payment.succeeded"}),
            frozenset({"order.returned", "payment.refunded"}),
            monetary_events=frozenset({"order.confirmed", "payment.succeeded", "payment.refunded"}),
        ),
        TemplateStrategy(
            "attended_booking",
            frozenset({"booking.created", "booking.attended"}),
            frozenset({"booking.no_show"}),
            (frozenset({"booking.attended", "booking.no_show"}),),
        ),
        TemplateStrategy(
            "qualified_lead_accepted",
            frozenset({"lead.captured", "lead.qualified", "lead.accepted"}),
            frozenset(),
        ),
        TemplateStrategy(
            "paid_activated_subscription",
            frozenset({"account.activated", "payment.succeeded"}),
            frozenset({"payment.refunded"}),
            monetary_events=frozenset({"payment.succeeded", "payment.refunded"}),
        ),
    )
}
