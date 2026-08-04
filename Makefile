.PHONY: install dev dev-web dev-api check test infra-up infra-down

install:
	pnpm install
	uv sync --project apps/api

dev:
	pnpm dev

dev-web:
	pnpm --filter @outcomeos/web dev

dev-api:
	uv run --project apps/api uvicorn outcomeos_api.main:app --reload

check:
	pnpm --filter @outcomeos/web check
	uv run --project apps/api ruff check apps/api
	uv run --project apps/api mypy apps/api/src

test:
	uv run --project apps/api pytest apps/api/tests

infra-up:
	docker compose up -d

infra-down:
	docker compose down
