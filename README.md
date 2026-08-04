# OutcomeOS

OutcomeOS is an early-stage platform for turning organizational goals into measurable outcomes. This repository is a pnpm/uv monorepo containing a Next.js web application, a FastAPI service, local infrastructure, and product and engineering documentation.

> **Current state:** foundation only. Authentication is a labeled demo mechanism, integrations are mocks, and neither may be enabled in production.

## Prerequisites

- Node.js 22+
- pnpm 10+
- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Docker with Compose

## Quick start

```bash
cp .env.example .env
make install
make infra-up
make dev
```

The web app runs at <http://localhost:3000>, the API at <http://localhost:8000>, MinIO at <http://localhost:9001>, PostgreSQL at `localhost:5432`, and Redis at `localhost:6379`.

## Commands

```bash
make install  # install frontend and backend dependencies
make dev      # run web and API together
make check    # lint/type-check both applications
make test     # run backend tests
make infra-up # start local dependencies
```

Operational probes are `GET /health` (process liveness), `GET /ready` (dependency
readiness), and `GET /worker-health` (background-worker/queue health). The existing
`GET /healthz` endpoint remains available for compatibility.

## Exact local and CI verification commands

Run these commands from the repository root after `make install`. They are the same checks
used by `.github/workflows/ci.yml`:

```bash
uv run --project apps/api ruff check apps/api scripts/validate_migrations.py
uv run --project apps/api ruff format --check apps/api scripts/validate_migrations.py
uv run --project apps/api mypy apps/api/src apps/api/tests
uv run --project apps/api pytest apps/api/tests --cov=outcomeos_api --cov-report=term-missing --cov-fail-under=90
uv run --project apps/api python scripts/validate_migrations.py
uv run --project apps/api detect-secrets scan --all-files --exclude-files 'pnpm-lock.yaml'
pnpm --filter @outcomeos/web lint
pnpm --filter @outcomeos/web typecheck
pnpm --filter @outcomeos/web test
pnpm --filter @outcomeos/web build
pnpm --filter @outcomeos/web exec playwright install chromium
pnpm --filter @outcomeos/web test:e2e
```

The API suite covers tenant isolation, RBAC, signed webhook replay windows, canonical event
idempotency, transactional outbox behavior, attribution boundaries, order validation and
concurrency, contract versions, append-only credits, and dispute finality. The AI evaluations
use a deterministic provider and require no API key, external model, or network call.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for system boundaries and [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md) for an honest capability inventory.
