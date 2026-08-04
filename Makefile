.PHONY: setup dev lint typecheck test test-e2e build seed migrate verify infra-up infra-down

setup:
	pnpm install --frozen-lockfile
	uv sync --project apps/api --frozen
	uv sync --project apps/worker --frozen

dev:
	@trap 'kill 0' INT TERM EXIT; \
	uv run --project apps/api uvicorn outcomeos_api.main:app --reload & \
	uv run --project apps/worker python -m outcomeos_worker & \
	pnpm --filter @outcomeos/web dev & wait

lint:
	pnpm lint
	uv run --project apps/api ruff check apps/api
	uv run --project apps/worker ruff check apps/worker

typecheck:
	pnpm typecheck
	uv run --project apps/api mypy apps/api/src apps/api/tests
	uv run --project apps/worker mypy apps/worker/src apps/worker/tests

test:
	pnpm test
	uv run --project apps/api pytest
	uv run --project apps/worker pytest

test-e2e:
	uv run --project apps/api pytest -m e2e

build:
	pnpm build
	uv build --project apps/api
	uv build --project apps/worker

seed:
	uv run --project apps/api python scripts/seed.py

migrate:
	uv run --project apps/api alembic -c apps/api/alembic.ini upgrade head

verify: lint typecheck test test-e2e build

infra-up:
	docker compose up -d --wait

infra-down:
	docker compose down
