from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from .common import TenantContext, new_id, now
from .tenancy import TenantStore


@dataclass(frozen=True, slots=True)
class ProviderMessage:
    external_id: str
    customer_ref: str
    text: str
    sandbox: bool


class MessageProvider(Protocol):
    name: str
    sandbox: bool

    def receive(self, payload: dict[str, str]) -> ProviderMessage: ...


class SandboxMessageProvider:
    name = "sandbox-messaging"
    sandbox = True

    def receive(self, payload: dict[str, str]) -> ProviderMessage:
        return ProviderMessage(payload["id"], payload["customer_ref"], payload["text"], True)


@dataclass(slots=True)
class Conversation:
    id: str
    tenant_id: str
    customer_ref: str
    messages: list[dict[str, object]] = field(default_factory=list)


class ConversationService:
    def __init__(self, store: TenantStore[Conversation] | None = None) -> None:
        self.store = store or TenantStore()

    def receive(self, ctx: TenantContext, provider: MessageProvider, payload: dict[str, str]) -> Conversation:
        message = provider.receive(payload)
        existing = self.store.find(ctx, lambda c: c.customer_ref == message.customer_ref)
        conversation = existing[0] if existing else Conversation(new_id("conv"), ctx.tenant_id, message.customer_ref)
        conversation.messages.append({"external_id": message.external_id, "text": message.text, "at": now(), "sandbox": message.sandbox})
        return self.store.put(ctx, conversation.id, conversation)
