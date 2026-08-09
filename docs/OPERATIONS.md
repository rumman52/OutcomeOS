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
