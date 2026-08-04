from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Callable, Generic, TypeVar

from .common import DomainError, TenantContext

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Tenant:
    id: str
    name: str


class TenantStore(Generic[T]):
    """In-memory reference store whose API makes cross-tenant reads impossible."""

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], T] = {}
        self.lock = RLock()

    def put(self, ctx: TenantContext, row_id: str, value: T) -> T:
        with self.lock:
            self._rows[(ctx.tenant_id, row_id)] = value
        return value

    def get(self, ctx: TenantContext, row_id: str) -> T:
        try:
            return self._rows[(ctx.tenant_id, row_id)]
        except KeyError as exc:
            raise DomainError(f"resource {row_id!r} not found") from exc

    def find(self, ctx: TenantContext, predicate: Callable[[T], bool] = lambda _: True) -> list[T]:
        return [v for (tenant, _), v in self._rows.items() if tenant == ctx.tenant_id and predicate(v)]
