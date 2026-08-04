# Integrations

## Status disclaimer

No external integration is operational. Any connector UI or fixture added during early development must be labeled **mock**, return synthetic data, and require `MOCK_INTEGRATIONS_ENABLED=true`. That flag is forbidden in production.

## Candidate integrations

| Provider category | Potential purpose | Status |
| --- | --- | --- |
| OIDC identity provider | Authentication and lifecycle | planned; not operational |
| Slack / Microsoft Teams | Reminders and check-ins | planned; not operational |
| Jira / Linear | Initiative delivery signals | planned; not operational |
| Salesforce | Commercial outcome signals | planned; not operational |
| Google Drive / Microsoft 365 | Evidence links and documents | planned; not operational |
| Email | Transactional notifications | planned; not operational |
| LLM provider | Assisted summaries with human review | exploratory; not operational |
| Payment service provider | Payment intent and settlement evidence | planned; not operational |
| Tax calculation provider | Quoted tax inputs | planned; not operational |
| Accounting platform | Invoice/payment export and reconciliation | planned; not operational |

## Connector contract

Each real adapter must support encrypted per-tenant credentials, least-privilege scopes, explicit consent, connection tests, idempotent synchronization, cursor checkpoints, retry/backoff, rate-limit handling, webhook signature verification, deletion, audit events, and clear freshness/error reporting.

Provider fixtures must never share interfaces that allow accidental network calls. Production startup and deployment tests must prove mock factories are unreachable.

## Evidence levels

`implemented` means adapter code and automated contract coverage exist. `sandbox-tested` additionally requires retained evidence from the provider's non-production environment. `live-tested` requires a controlled real-environment operation, webhook/response verification, and reconciliation to internal immutable facts. These labels are independent: neither a mock nor a successful sandbox request may be called live, and live-tested does not automatically mean approved for general production use. The authoritative capability labels live in `IMPLEMENTATION_STATUS.md`.

## Financial provider boundary

OutcomeOS remains authoritative for its own orders, invoices, allocation history, and audit trail. Provider requests use stable tenant-scoped idempotency keys and persist opaque external references. Webhooks are untrusted duplicate/out-of-order messages: verify signature and freshness, store receipt metadata, process idempotently, and reconcile rather than overwriting issued facts. Currency and minor-unit interpretation must match provider metadata. Provider refunds, disputes, tax adjustments, and settlement differences become explicit linked facts or exceptions.
