# OutcomeOS

OutcomeOS is an emerging global, multi-tenant outcome verification and performance billing platform. Its goal is to connect customer journeys to trusted business evidence, determine whether contracted outcomes occurred, calculate exact fees, manage disputes and credits, and deliver consent-aware conversion postbacks.

The repository is being incrementally transformed from a country-specific deterministic demo. The legacy journey remains sandbox-only while global domain and PostgreSQL foundations replace it. No real advertising, messaging, commerce, payment, identity, fulfilment or hosted-AI provider is currently connected, and this repository is not yet production-ready.

## Quick start

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

## Commands

`make setup`, `make install`, `make dev`, `make dev-web`, `make dev-api`, `make dev-worker`, `make lint`, `make typecheck`, `make test`, `make test-integration`, `make e2e`, `make build`, `make migrations-check`, `make migrate`, `make seed`, `make verify`, `make infra-up`, and `make infra-down` are the canonical command surface.

Run `make verify` before proposing changes. `make e2e` requires running web/API services.

See the execution plan in `docs/superpowers/plans/2026-08-08-outcomeos-global-platform.md` and the evidence-based status in `docs/IMPLEMENTATION_STATUS.md`. The genuine pnpm lockfile passes frozen installation. A genuine uv lockfile is still blocked on registry access and will never be hand-written.
