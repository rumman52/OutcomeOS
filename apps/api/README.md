# OutcomeOS API persistence

This package defines the MVP SQLAlchemy schema and its initial Alembic migration.

## Tenant boundary

Application entry points resolve an active `Membership` with
`authenticated_tenant_transaction`; the transaction then sets PostgreSQL's
transaction-local `app.tenant_id`. Callers must use `TenantRepository` rather
than accepting a tenant identifier in business service payloads. High-risk
tables additionally use forced, fail-closed PostgreSQL row-level security for
both reads and writes.

Background producers sign `JobTenantContext`; consumers verify it before
opening a tenant transaction. Object storage and caches use the helpers in
`tenancy.py`, which put the tenant at the start of every namespace.

## Commands

```bash
python -m pip install -e '.[test]'
alembic upgrade head
pytest
```

Production application roles must not be superusers and must not have the
`BYPASSRLS` attribute. `FORCE ROW LEVEL SECURITY` also applies policies to the
table owner.
