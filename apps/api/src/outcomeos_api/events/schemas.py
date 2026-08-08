from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProcessingStatus(StrEnum):
    RECEIVED = "received"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class EventMoney(BaseModel):
    model_config = ConfigDict(frozen=True)
    minor_units: int
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class ConsentFlags(BaseModel):
    model_config = ConfigDict(frozen=True)
    processing_permitted: bool
    advertising_permitted: bool = False
    purpose: str = Field(min_length=1, max_length=200)


class CanonicalEvent(BaseModel):
    """Version 1 canonical envelope; raw provider objects never enter domain records."""

    model_config = ConfigDict(frozen=True)
    event_id: UUID
    tenant_id: UUID
    provider: str = Field(min_length=1, max_length=80)
    source_type: str = Field(min_length=1, max_length=80)
    provider_event_id: str | None = Field(default=None, max_length=255)
    payload_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    event_type: str = Field(pattern=r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
    schema_version: int = Field(default=1, ge=1)
    occurred_at: datetime
    received_at: datetime
    subject_type: str = Field(min_length=1, max_length=80)
    subject_id: str = Field(min_length=1, max_length=255)
    references: dict[str, str] = Field(default_factory=dict)
    attribution: dict[str, str] = Field(default_factory=dict)
    money: EventMoney | None = None
    consent: ConsentFlags
    payload: dict[str, Any]
    raw_object_key: str | None = None
    raw_payload_digest: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    processing_status: ProcessingStatus = ProcessingStatus.RECEIVED
    error_code: str | None = None

    @field_validator("occurred_at", "received_at")
    @classmethod
    def require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamps must include a UTC offset")
        return value
