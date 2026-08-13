.PHONY: setup install dev dev-web dev-api dev-worker lint typecheck test test-web test-api test-integration e2e build migrations-check migrate seed verify infra-up infra-down

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
	uv run --project apps/api ruff check apps/api scripts/validate_migrations.py
	uv run --project apps/api ruff format --check apps/api scripts/validate_migrations.py

typecheck:
	pnpm typecheck
	uv run --project apps/api mypy --config-file apps/api/pyproject.toml apps/api/src apps/api/tests

test:
	$(MAKE) test-web
	$(MAKE) test-api

test-web:
	pnpm test

test-api:
	uv run --project apps/api pytest apps/api/tests --ignore=apps/api/tests/integration --cov=outcomeos_api --cov-report=term-missing --cov-fail-under=90

test-integration:
	uv run --project apps/api pytest apps/api/tests/integration -m integration

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

verify: lint typecheck test test-integration build migrations-check e2e
	git diff --check

infra-up:
	docker compose up -d

infra-down:
	docker compose down
