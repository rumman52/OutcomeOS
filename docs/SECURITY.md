# Security

## Invariants preserved in the local MVP

- Tenant context is server-side demo membership context; clients cannot authorize arbitrary tenants.
- Business records carry `tenant_id` in the deterministic store and canonical SQLAlchemy model boundary.
- Money is integer minor units plus ISO currency.
- Side-effecting demo workflow uses idempotency keys and repeated approval does not double bill.
- Signed sandbox webhooks require timestamp and HMAC verification before business handling.
- Deterministic AI does not call a network provider and stores evidence references.
- Dispute reversal appends a linked credit instead of editing/deleting the original ledger fact.
- Demo/mock features, deterministic AI defaults, and default webhook secrets are rejected when `APP_ENV=production`.

## Remaining security work

Full PostgreSQL RLS enforcement, composite tenant foreign keys across the entire required schema, production OIDC, secrets management, rate limiting, object quarantine, backup/restore evidence, and threat-model signoff remain required before production use.
