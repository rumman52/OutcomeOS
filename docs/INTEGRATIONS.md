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

## Connector contract

Each real adapter must support encrypted per-tenant credentials, least-privilege scopes, explicit consent, connection tests, idempotent synchronization, cursor checkpoints, retry/backoff, rate-limit handling, webhook signature verification, deletion, audit events, and clear freshness/error reporting.

Provider fixtures must never share interfaces that allow accidental network calls. Production startup and deployment tests must prove mock factories are unreachable.
