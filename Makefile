.PHONY: setup install dev dev-web dev-api dev-worker lint typecheck test test-e2e e2e build migrations-check migrate seed verify infra-up infra-down

setup install:
	pnpm install --frozen-lockfile
	uv sync --project apps/api --frozen

dev:
	@trap 'kill 0' INT TERM EXIT; \
	uv run --project apps/api uvicorn outcomeos_api.main:app --reload & \
	uv run --project apps/worker python -m outcomeos_worker & \
	pnpm --filter @outcomeos/web dev & wait

dev-web:
	pnpm --filter @outcomeos/web dev

dev-api:
	uv run --project apps/api uvicorn outcomeos_api.main:app --reload

dev-worker:
	uv run --project apps/worker python -m outcomeos_worker

lint:
	pnpm lint
	uv run --project apps/api ruff check apps/api

typecheck:
	pnpm typecheck
	uv run --project apps/api mypy apps/api/src apps/api/tests

test:
	pnpm test
	uv run --project apps/api pytest apps/api/tests

test-e2e:
	uv run --project apps/api pytest -m e2e apps/api/tests

e2e:
	pnpm e2e

build:
	pnpm build
	uv build --project apps/api
	uv build --project apps/worker

migrations-check:
	python3 scripts/validate_migrations.py
	uv run --project apps/api alembic -c apps/api/alembic.ini check

migrate:
	uv run --project apps/api alembic -c apps/api/alembic.ini upgrade head

seed:
	uv run --project apps/api python scripts/seed.py

verify: lint typecheck test test-e2e e2e build migrations-check

infra-up:
	docker compose up -d --wait

infra-down:
	docker compose down
