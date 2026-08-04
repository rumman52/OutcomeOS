from __future__ import annotations

from dataclasses import dataclass

from .common import DomainError


@dataclass(frozen=True, slots=True)
class DeliveryEvidence:
    tracking_id: str
    delivered_at: str
    recipient: str

    def validate(self) -> None:
        if not all((self.tracking_id, self.delivered_at, self.recipient)):
            raise DomainError("complete delivery evidence is required")


def verify_outcome(evidence: DeliveryEvidence | None, cod_settled: bool) -> None:
    if evidence is None:
        raise DomainError("delivery evidence is required")
    evidence.validate()
    if not cod_settled:
        raise DomainError("COD settlement is required")
