from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping, Any

from .common import DomainError

AllowedTool = Literal["create_lead", "create_order"]


@dataclass(frozen=True, slots=True)
class ToolProposal:
    tool: AllowedTool
    arguments: Mapping[str, Any]
    rationale: str


class ProposalValidator:
    schemas = {
        "create_lead": frozenset({"customer_ref", "name", "contact"}),
        "create_order": frozenset({"lead_id", "sku", "quantity", "unit_price", "currency", "authorization"}),
    }

    def validate(self, raw: Mapping[str, Any]) -> ToolProposal:
        tool = raw.get("tool")
        if tool not in self.schemas or not isinstance(raw.get("arguments"), dict):
            raise DomainError("unknown or malformed AI tool proposal")
        if set(raw["arguments"]) != self.schemas[tool]:
            raise DomainError("proposal arguments do not match schema")
        return ToolProposal(tool, dict(raw["arguments"]), str(raw.get("rationale", "")))


def propose_from_message(text: str, knowledge: list[object]) -> ToolProposal:
    """Deterministic sandbox AI adapter; proposals never execute themselves."""
    raw = {"tool": "create_lead", "arguments": {"customer_ref": "customer-1", "name": "Sandbox Customer", "contact": text}, "rationale": f"grounded in {len(knowledge)} tenant documents"}
    return ProposalValidator().validate(raw)
