.PHONY: install dev worker db-up db-down migrate test lint fmt eval-smoke bench

install:
	uv sync --all-extras

dev:
	uv run uvicorn webnovel.entrypoints.api.app:create_app --factory --reload --port 8000

worker:
	uv run python -m webnovel.entrypoints.worker.main

db-up:
	docker compose up -d postgres redis

db-down:
	docker compose down

migrate:
	uv run alembic upgrade head

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run mypy src
	uv run lint-imports

fmt:
	uv run ruff format .

eval-smoke:
	uv run python -m webnovel.entrypoints.cli eval --suite smoke

eval-full:
	uv run python -m webnovel.entrypoints.cli eval --suite full

bench:
	uv run python -m webnovel.entrypoints.cli bench
