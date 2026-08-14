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
- `GET /worker-health`: degraded until a real worker heartbeat exists.
# Event evidence storage

Configure `S3_ENDPOINT_URL`, bucket and credentials, object byte limits, and TLS policy. Configure
`INTEGRATION_KEYRING` and `INTEGRATION_ACTIVE_KEY_ID` from a secret manager and retain old keys only
for the bounded rotation interval. Object retention is an operator-owned bucket lifecycle policy;
the application adapter performs deletion only when an authorized future service requests it.

Migration `20260814_0003` is additive and supports downgrade to `20260808_0002`. Before promotion,
exercise upgrade, restricted-role forced RLS, append-only protections, composite foreign keys, and
the downgrade/upgrade round trip on disposable PostgreSQL. Part 1 has no worker, replay, CSV parser,
or reconciliation command to operate.

## Signed ingress

Ingress has configured body and replay-window limits. Evidence uses deterministic tenant-prefixed keys, conditional creation, digest metadata, and server-side encryption. A database rollback can leave an identical deterministic object orphan for future Part 3 reconciliation. Delivery remains at-least-once; this part adds no worker.
