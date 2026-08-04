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
- `GET /ready`: local persistent demo-store availability; PostgreSQL RLS is not claimed by this response.
- `GET /worker-health`: degraded until a real worker heartbeat exists.
