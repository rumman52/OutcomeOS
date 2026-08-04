from __future__ import annotations

from dataclasses import dataclass

from .common import TenantContext


@dataclass(frozen=True, slots=True)
class KnowledgeItem:
    tenant_id: str
    text: str
    tags: frozenset[str]


class KnowledgeIndex:
    def __init__(self) -> None:
        self._items: list[KnowledgeItem] = []

    def add(self, item: KnowledgeItem) -> None:
        self._items.append(item)

    def retrieve(self, ctx: TenantContext, query: str, limit: int = 3) -> list[KnowledgeItem]:
        terms = set(query.lower().split())
        scoped = [i for i in self._items if i.tenant_id == ctx.tenant_id]
        return sorted(scoped, key=lambda i: len(terms & (set(i.text.lower().split()) | set(i.tags))), reverse=True)[:limit]


def dashboard_metrics(outcomes: list[object], ledger: list[object]) -> dict[str, int]:
    return {"outcomes": len(outcomes), "ledger_entries": len(ledger)}
