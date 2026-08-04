# OutcomeOS

OutcomeOS is an early-stage platform for connecting commercial operations to measurable outcomes. Its first planned vertical slice is a persistent, auditable order-to-billing demo journey. This repository is a pnpm/uv monorepo containing a Next.js web application, a FastAPI service, reserved worker/shared-contract boundaries, local infrastructure, and product and engineering documentation.

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
make setup    # install strictly from frontend and backend lockfiles
make dev      # run web and API together
make lint     # lint TypeScript and Python
make typecheck # strictly type-check both ecosystems
make test     # run unit/integration tests
make e2e      # run the E2E harness
make build    # create production builds
make migrations-check # validate migration structure
make seed     # run the safe seed entry point
make verify   # aggregate non-destructive quality checks
make infra-up # start local dependencies
```

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for system boundaries and [`docs/IMPLEMENTATION_STATUS.md`](docs/IMPLEMENTATION_STATUS.md) for an honest capability inventory.
