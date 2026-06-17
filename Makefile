.PHONY: install dev run test lint fmt typecheck

install:
	uv sync

dev:
	uv run uvicorn proxy.main:app --reload --app-dir src

run:
	uv run uvicorn proxy.main:app --host 0.0.0.0 --port 8000 --app-dir src

test:
	uv run pytest

lint:
	uv run ruff check .

typecheck:
	uv run mypy

fmt:
	uv run ruff format . && uv run ruff check --fix .
