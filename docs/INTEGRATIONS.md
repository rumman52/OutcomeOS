# Integrations

## Current status

All provider-facing capabilities are deterministic sandbox/mock behavior. Real Meta, WhatsApp/Messenger, Google, TikTok, Pathao/courier, COD/payment, OIDC, and hosted AI connections are **NOT CONNECTED**. No sandbox-tested, live-tested, or production-ready external integration is claimed.

## Implemented sandbox boundaries

- Meta-like campaign/ad/spend fixture.
- WhatsApp/Messenger-like inbound message fixture.
- Signed sandbox delivery and COD webhook endpoints.

## Event foundation (not a live connection)

Provider-neutral endpoint management and `POST /api/v1/webhooks/{public_token}` are implemented on
the PostgreSQL path. The public route resolves endpoint material through the restricted ingress
function, authenticates exact request bytes before strict JSON validation, stores server-side
encrypted raw evidence, and atomically creates a receipt, canonical event, and pending durable job.
Identical retries reuse the existing result and conflicting payloads are rejected. This is an
ingestion boundary, not a provider SDK integration or background execution. S3 compatibility is
tested against disposable MinIO; this does not represent a live provider connection.
- Deterministic OTP/intent/risk verification checks.
- Deterministic AI provider output grounded in tenant knowledge.

Production startup rejects demo/mock flags, deterministic AI defaults, and default webhook secrets.
Future real adapters must still add provider-specific contracts, retry/backoff, deletion, audit,
freshness/error UI, and provider certification.

## Provider-neutral endpoint lifecycle

Creation and rotation disclose a new signing secret once; list and detail never expose secrets, ciphertext, nonces, or key IDs. Rotation permits only a configured bounded overlap. Part 2 connects no live provider.
