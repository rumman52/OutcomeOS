# Operations

## Local demo journey

```bash
cp .env.example .env
make setup
make infra-up
make migrate
make seed
make dev
# another terminal
make dev-worker
```

`make verify` runs available non-destructive checks. Playwright E2E can be run with `make e2e` after web/API services are running.

## Probes

- `GET /health`: process liveness only.
- `GET /ready`: PostgreSQL connectivity and migration-head readiness. An explicitly selected local/test JSON sandbox reports itself honestly.
- `GET /worker-health`: returns healthy only for a fresh healthy heartbeat; draining, stale,
  missing, and database-unavailable states fail closed with HTTP 503.
# Event evidence storage

Configure `S3_ENDPOINT_URL`, bucket and credentials, object byte limits, and TLS policy. Configure
`INTEGRATION_KEYRING` and `INTEGRATION_ACTIVE_KEY_ID` from a secret manager and retain old keys only
for the bounded rotation interval. Object retention is an operator-owned bucket lifecycle policy;
the application adapter performs deletion only when an authorized future service requests it.

Migration `20260814_0003` is additive and supports downgrade to `20260808_0002`. Before promotion,
exercise upgrade, restricted-role forced RLS, append-only protections, composite foreign keys, and
the downgrade/upgrade round trip on disposable PostgreSQL. Part 3 adds the durable worker, replay,
CSV import, and reconciliation commands; all remain pre-production until mandatory CI passes.

## Signed ingress

Ingress has configured body and replay-window limits. Evidence uses deterministic tenant-prefixed keys, conditional creation, digest metadata, and server-side encryption. A database rollback can leave an identical deterministic object orphan for future Part 3 reconciliation. Delivery remains at-least-once; this part adds no worker.
# Durable worker operations

The PostgreSQL worker is run with `python -m outcomeos_api.worker`; `--once` claims one bounded
batch for operational testing. Claims use database leases and deterministic retry delays. A
SIGTERM or SIGINT stops new polling and records draining state. `/worker-health` is successful
only for a fresh healthy heartbeat and otherwise fails closed without revealing worker identity
or connection details.

Part 2's verified baseline is commit `3e3f744411e68eaeb9d54e5a5569788bd7240121`, workflow
`31829054612`.
