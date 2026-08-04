# Integrations

## Current status

All provider-facing capabilities are deterministic sandbox/mock behavior. Real Meta, WhatsApp/Messenger, Google, TikTok, Pathao/courier, COD/payment, OIDC, and hosted AI connections are **NOT CONNECTED**. No sandbox-tested, live-tested, or production-ready external integration is claimed.

## Implemented sandbox boundaries

- Meta-like campaign/ad/spend fixture.
- WhatsApp/Messenger-like inbound message fixture.
- Signed sandbox delivery and COD webhook endpoints.
- Deterministic OTP/intent/risk verification checks.
- Deterministic AI provider output grounded in tenant knowledge.

Production startup rejects demo/mock flags, deterministic AI defaults, and default webhook secrets. Future real adapters must add encrypted tenant credentials, least-privilege scopes, webhook signature/replay validation, idempotency, retry/backoff, deletion, audit, freshness/error UI, contract tests, and retained provider evidence.
