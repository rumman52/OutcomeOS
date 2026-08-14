from __future__ import annotations

import hashlib
import hmac
import re
from collections.abc import Iterable
from datetime import UTC, datetime

_SIGNATURE = re.compile(r"v1=([0-9a-f]{64})\Z")
_TIMESTAMP = re.compile(rb"0|[1-9][0-9]{0,12}\Z")


class SignatureError(ValueError):
    """A sanitized authentication failure safe to translate to HTTP 401."""


def parse_timestamp(value: bytes) -> int:
    if not _TIMESTAMP.fullmatch(value):
        raise SignatureError("invalid webhook authentication")
    return int(value)


def parse_signature(values: list[str]) -> bytes:
    if len(values) != 1:
        raise SignatureError("invalid webhook authentication")
    match = _SIGNATURE.fullmatch(values[0])
    if match is None:
        raise SignatureError("invalid webhook authentication")
    return bytes.fromhex(match.group(1))


def sign(secret: bytes, timestamp_header: bytes, body: bytes) -> str:
    return hmac.new(secret, timestamp_header + b"." + body, hashlib.sha256).hexdigest()


def authenticate(
    *,
    secrets: Iterable[bytes],
    timestamp_header: bytes,
    signature_headers: list[str],
    body: bytes,
    replay_window_seconds: int,
    now: datetime | None = None,
) -> None:
    timestamp = parse_timestamp(timestamp_header)
    checked_at = int((now or datetime.now(UTC)).timestamp())
    if abs(checked_at - timestamp) > replay_window_seconds:
        raise SignatureError("invalid webhook authentication")
    supplied = parse_signature(signature_headers)
    # Evaluate all usable versions rather than leaking which rotation version matched.
    matched = False
    for secret in secrets:
        expected = hmac.new(secret, timestamp_header + b"." + body, hashlib.sha256).digest()
        matched = hmac.compare_digest(expected, supplied) or matched
    if not matched:
        raise SignatureError("invalid webhook authentication")
