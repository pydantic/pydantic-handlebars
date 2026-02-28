.PHONY: install format lint typecheck test testcov all

install:
	uv sync --frozen --all-groups

format:
	uv run ruff format
	uv run ruff check --fix

lint:
	uv run ruff format --check
	uv run ruff check

typecheck:
	uv run pyright

test:
	uv run pytest

testcov:
	uv run coverage run -m pytest
	uv run coverage report

all: format lint typecheck testcov
