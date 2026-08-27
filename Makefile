.PHONY: check lint format type test docs-check install status

install:
	uv sync

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff format .
	uv run ruff check --fix .

type:
	uv run mypy

docs-check:
	uv run python tools/check_decisions.py

test:
	uv run pytest

check: lint type docs-check test

status:
	uv run python tools/plan_status.py
