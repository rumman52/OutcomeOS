# Security

## Baseline principles

- Deny by default and authorize every tenant-scoped operation server-side.
- Store no secrets in source control; inject and rotate them through a secret manager.
- Encrypt traffic in transit and provider-managed data at rest.
- Minimize collected data and define retention and deletion policies before launch.
- Record security-relevant actions in tamper-resistant audit logs.

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
