from typing import Protocol

from outcomeos_api.models import CreateOrderArgs, StockLookupArgs
from outcomeos_api.store import Store


TOOL_SCHEMAS = {
    "lookup_stock": StockLookupArgs.model_json_schema(),
    "create_order": CreateOrderArgs.model_json_schema(),
}


class AIAdapter(Protocol):
    def reply(self, message: str) -> str: ...


class DeterministicMockAI:
    """Offline demo adapter; deliberately incapable of provider calls."""

    def reply(self, message: str) -> str:
        normalized = message.casefold()
        if any(word in normalized for word in ("human", "agent", "মানুষ", "অভিযোগ")):
            return "HANDOFF_REQUIRED"
        if any(word in normalized for word in ("delivery", "ডেলিভারি")):
            return "ঢাকার ভিতরে 2–3 দিন। Outside Dhaka delivery takes 3–5 days."
        return "আমি পণ্য, স্টক ও অর্ডারে সাহায্য করতে পারি। I can help with products, stock, and orders."


def execute_tool(store: Store, name: str, raw_arguments: object) -> object:
    """Pydantic validation is mandatory at this server-side trust boundary."""
    if name == "lookup_stock":
        args = StockLookupArgs.model_validate(raw_arguments)
        return {"on_hand": store.stock(args.tenant_id, args.variant_id)}
    if name == "create_order":
        args = CreateOrderArgs.model_validate(raw_arguments)
        return store.create_order(args)
    raise ValueError("unknown tool")
