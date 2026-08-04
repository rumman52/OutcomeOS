.PHONY: setup install dev dev-web dev-api dev-worker lint typecheck test test-integration e2e build migrations-check migrate seed verify infra-up infra-down

setup install:
	pnpm install --frozen-lockfile
	uv sync --project apps/api --frozen

dev:
	pnpm dev

dev-web:
	pnpm --filter @outcomeos/web dev

dev-api:
	uv run --project apps/api uvicorn outcomeos_api.main:app --reload

dev-worker:
	uv run --project apps/api python -m outcomeos_api.worker

lint:
	pnpm lint
	uv run --project apps/api ruff check apps/api

typecheck:
	pnpm typecheck
	uv run --project apps/api mypy apps/api/src apps/api/tests

test:
	pnpm test
	uv run --project apps/api pytest apps/api/tests

test-integration:
	uv run --project apps/api pytest apps/api/tests -m "not e2e"

e2e:
	pnpm e2e

build:
	pnpm build
	uv build --project apps/api

migrations-check:
	uv run --project apps/api python scripts/validate_migrations.py

migrate:
	uv run --project apps/api alembic -c apps/api/alembic.ini upgrade head

seed:
	uv run --project apps/api python scripts/seed.py

verify: lint typecheck test build migrations-check
	@echo "E2E available via make e2e after starting web/API"

infra-up:
	docker compose up -d

infra-down:
	docker compose down
