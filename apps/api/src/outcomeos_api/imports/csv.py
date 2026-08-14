from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass

from outcomeos_api.events.schemas import PublicEventInput

CSV_V1_HEADERS = (
    "provider_event_id",
    "event_type",
    "occurred_at",
    "subject_type",
    "subject_id",
    "processing_permitted",
    "advertising_permitted",
    "consent_purpose",
    "references_json",
    "attribution_json",
    "money_minor_units",
    "money_currency",
    "payload_json",
)


@dataclass(frozen=True)
class CsvLimits:
    bytes: int
    rows: int
    columns: int
    field_length: int


def parse_csv_v1(body: bytes, limits: CsvLimits) -> list[PublicEventInput]:
    if len(body) > limits.bytes:
        raise ValueError("csv_bytes_exceeded")
    try:
        source = body.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ValueError("csv_utf8_required") from error
    reader = csv.reader(io.StringIO(source, newline=""), strict=True)
    try:
        headers = next(reader)
    except (StopIteration, csv.Error) as error:
        raise ValueError("csv_header_invalid") from error
    if len(headers) != len(set(headers)) or tuple(headers) != CSV_V1_HEADERS:
        raise ValueError("csv_header_invalid")
    if len(headers) > limits.columns:
        raise ValueError("csv_columns_exceeded")
    events: list[PublicEventInput] = []
    for number, values in enumerate(reader, start=2):
        if number - 1 > limits.rows:
            raise ValueError("csv_rows_exceeded")
        if len(values) != len(headers) or any(len(value) > limits.field_length for value in values):
            raise ValueError(f"csv_row_invalid:{number}")
        row = dict(zip(headers, values, strict=True))
        money = None
        if row["money_minor_units"] or row["money_currency"]:
            money = {
                "minor_units": int(row["money_minor_units"]),
                "currency": row["money_currency"],
            }
        events.append(
            PublicEventInput.model_validate(
                {
                    "provider_event_id": row["provider_event_id"],
                    "event_type": row["event_type"],
                    "occurred_at": row["occurred_at"],
                    "subject_type": row["subject_type"],
                    "subject_id": row["subject_id"],
                    "consent": {
                        "processing_permitted": row["processing_permitted"].lower() == "true",
                        "advertising_permitted": row["advertising_permitted"].lower() == "true",
                        "purpose": row["consent_purpose"],
                    },
                    "references": json.loads(row["references_json"] or "{}"),
                    "attribution": json.loads(row["attribution_json"] or "{}"),
                    "money": money,
                    "payload": json.loads(row["payload_json"]),
                }
            )
        )
    return events
