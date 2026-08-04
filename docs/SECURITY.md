# Security

## Baseline principles

- Deny by default and authorize every tenant-scoped operation server-side.
- Store no secrets in source control; inject and rotate them through a secret manager.
- Encrypt traffic in transit and provider-managed data at rest.
- Minimize collected data and define retention and deletion policies before launch.
- Record security-relevant actions in tamper-resistant audit logs.

## Tenant isolation contract

Authenticated server-side identity establishes the tenant context; request bodies and route parameters cannot establish authority. Every tenant-owned row, cache key, object key, job, event, audit entry, and provider credential carries `tenant_id`. Application repositories require that context and planned database row-level security supplies defense in depth. Cross-tenant negative tests must cover direct identifiers, collections, search, export, background work, signed object access, and administrative paths.

Financial commands are also tenant-scoped, idempotent, and transactional. Accepted orders and issued invoices are not edited in place. Money is integer minor units plus currency; calculations reject currency mismatch and non-reconciling totals. Audit, idempotency, financial facts, and outbox intent commit together.

## Demo safety invariant

`DEMO_AUTH_ENABLED` and `MOCK_INTEGRATIONS_ENABLED` are local demonstration switches, not security or connectivity features. The API configuration validator and Next.js configuration reject either switch when the runtime is production. Deployment policy must additionally omit these flags or set them to `false`. Demo identities must never be accepted by a production API.

## Threats and required controls

| Threat | Required control | Current state |
| --- | --- | --- |
| Cross-tenant access | Tenant-scoped queries plus authorization tests | not implemented |
| Account takeover | OIDC, MFA policy, secure sessions, revocation | not implemented |
| Credential leakage | Secret manager, envelope encryption, log redaction | not implemented |
| Malicious uploads | Size/type limits, malware scan, quarantined bucket | not implemented |
| Injection | Typed validation, parameterized queries, output encoding | partial foundation |
| Abuse | Rate limiting, quotas, anomaly alerts | not implemented |

## Production checklist

Complete a threat model, dependency and container scanning, SAST, access review, backup restore exercise, incident-response runbook, penetration test, privacy review, and demo-mode negative test before production approval.

Report vulnerabilities privately to the repository owners; do not open a public issue containing exploit details.

## Sensitive data and integrations

Secrets are injected by a secret manager, rotated, excluded from browser bundles, and redacted from telemetry. Per-tenant connector credentials require envelope encryption and narrowly scoped runtime access. Webhooks require signature and timestamp/replay verification before any business parsing. Uploads remain quarantined until type, size, and malware checks complete. Data classification, retention, subject export/deletion, breach response, and log redaction rules must be approved before production data is accepted.
