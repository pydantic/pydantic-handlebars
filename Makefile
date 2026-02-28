.PHONY: .uv .prek install format lint typecheck test testcov fuzz all

.uv:
	@uv --version || echo 'Please install uv: https://docs.astral.sh/uv/getting-started/installation/'

.prek:
	@prek --version || echo 'Please install prek: https://github.com/j178/pre-commit-rs'

install: .uv .prek
	uv sync --frozen --all-groups
	prek install --install-hooks

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

fuzz:
	FUZZ_EXTENDED=1 uv run pytest tests/test_fuzz.py -x -s

all: format lint typecheck testcov
