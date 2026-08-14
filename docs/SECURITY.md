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

## Milestone 1 security boundary

Additive schema and application code now define provider-neutral OIDC/JWKS verification, persisted
identity-to-membership resolution, explicit role permissions, hashed scoped API keys, expanded RLS,
immutable tenant identifiers, and composite tenant foreign keys. No live identity provider is
claimed. The PostgreSQL enforcement suite must pass under its restricted `NOBYPASSRLS` role before
these controls can be described as operationally verified.
# Milestone 2 foundation

Integration secrets are encrypted with AES-256-GCM. Tenant ID, endpoint ID, format version, and
secret version form authenticated additional data, so ciphertext cannot be moved between tenants,
endpoints, or versions. Rotation retains explicit validity windows and key IDs; applications must
obtain keyring values from a production secret manager and must never log plaintext or ciphertext.

Staging and production startup fails closed when integration key identifiers are absent, local S3
credentials are retained, or TLS-required object storage uses a plaintext endpoint. Database RLS is
forced and tenant-owned append-only evidence rejects update and delete operations.
