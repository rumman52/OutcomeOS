# OutcomeOS

OutcomeOS is a local competition MVP for a Bangladesh e-commerce performance-marketing journey: sandbox campaign/touchpoint → customer conversation → grounded AI proposal → approved lead/order → verification → delivery and COD evidence → verified outcome → BDT 150 performance fee → BDT 340 contribution profit → dispute credit.

All provider behavior is deterministic sandbox/mock behavior. Real Meta, WhatsApp, Google, TikTok, Pathao, payment, OIDC, and hosted AI providers are **NOT CONNECTED**.

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

See `docs/DEMO.md`, `docs/IMPLEMENTATION_STATUS.md`, and `docs/REPOSITORY_AUDIT.md`.
