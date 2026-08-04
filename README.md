# OutcomeOS

OutcomeOS is an early-stage platform for turning organizational goals into measurable outcomes. The
repository contains a Next.js web shell, FastAPI API, separate Python worker shell, PostgreSQL local
infrastructure, and Alembic migrations.

> **Capability notice:** this is a foundation, not a production-ready product. Authentication and
> integrations are not implemented. The demo/mock switches fail closed in production.

## Prerequisites

- Node.js 22 or newer and pnpm 10.28
- Python 3.12 or newer and [uv](https://docs.astral.sh/uv/)
- Docker Engine with Docker Compose
- GNU Make

## Setup and first run

```bash
cp .env.example .env        # replace the local PostgreSQL password in both relevant values
make setup                  # installs exactly the committed lockfiles
make infra-up               # starts PostgreSQL and waits for health
make migrate                # applies the schema
make seed                   # optional idempotent example row
make dev                    # starts web, API, and worker; Ctrl-C stops all three
```

The web application is at <http://localhost:3000>. The API is at <http://localhost:8000>, with
liveness at `/health`, dependency readiness at `/ready`, and interactive docs at `/docs`.

## Commands

| Command | Purpose |
| --- | --- |
| `make setup` | Install pnpm and both uv environments from frozen lockfiles |
| `make dev` | Run web, API, and worker concurrently |
| `make lint` | Run ESLint and Ruff |
| `make typecheck` | Run strict TypeScript and mypy checks |
| `make test` | Run web, API, and worker unit tests |
| `make test-e2e` | Run application-boundary API tests |
| `make build` | Run the Next.js production build and build both Python wheels |
| `make seed` | Add idempotent local sample data |
| `make migrate` | Apply all Alembic migrations |
| `make verify` | Run lint, typecheck, tests, end-to-end tests, and production builds |

`make verify` uses normal Make prerequisites without ignored errors, so it stops and returns nonzero
as soon as a quality gate fails.

## Troubleshooting

- **Compose reports a required variable is missing:** copy `.env.example` to `.env` and set all
  `POSTGRES_*` values. Keep `DATABASE_URL` consistent with them.
- **`/ready` returns 503 or the worker exits:** run `make infra-up`, inspect `docker compose ps` and
  `docker compose logs postgres`, then check that `DATABASE_URL` uses the exposed port and password.
- **Migrations fail after changing local credentials:** an existing Docker volume retains the old
  credentials. If its data is disposable, run `make infra-down`, then
  `docker volume rm outcomeos_postgres-data` and start again.
- **Ports 3000, 5432, or 8000 are busy:** stop the conflicting process. PostgreSQL's host port may
  be changed with `POSTGRES_PORT`; update `DATABASE_URL` to match.
- **Frozen installation fails:** confirm the required pnpm and uv versions. Deliberately update a
  dependency with an unfrozen install, review the resulting lockfile, and commit manifest and lockfile
  together rather than bypassing frozen installs.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for technology and process boundaries and
[`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md) for the capability inventory.
