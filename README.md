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

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for system boundaries and [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md) for an honest capability inventory.
