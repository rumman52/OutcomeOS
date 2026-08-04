from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class Money(BaseModel):
    minor: int
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class OutcomeStage(StrEnum):
    CAPTURED = "captured"
    QUALIFIED = "qualified"
    CONVERTED = "converted"
    VERIFIED = "verified"
    DISQUALIFIED = "disqualified"


class ChatRequest(BaseModel):
    tenant_id: str
    session_id: str = Field(min_length=8, max_length=100)
    message: str = Field(min_length=1, max_length=2000)
    phone: str | None = Field(default=None, pattern=r"^\+?[0-9]{8,15}$")


class StockLookupArgs(BaseModel):
    tenant_id: str
    variant_id: str


class OrderItem(BaseModel):
    variant_id: str
    quantity: int = Field(ge=1, le=20)


class CreateOrderArgs(BaseModel):
    tenant_id: str
    contact_id: str
    items: list[OrderItem] = Field(min_length=1, max_length=20)
    payment_method: str = Field(pattern=r"^(cod|prepaid)$")
    delivery_address: str = Field(min_length=8, max_length=500)
    idempotency_key: str = Field(min_length=8, max_length=100)

    @field_validator("items")
    @classmethod
    def unique_variants(cls, items: list[OrderItem]) -> list[OrderItem]:
        if len({item.variant_id for item in items}) != len(items):
            raise ValueError("variant_id must be unique")
        return items
