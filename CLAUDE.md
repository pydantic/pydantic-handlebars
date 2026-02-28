# pydantic-handlebars

Pure Python implementation of the Handlebars template language.

## Quick Reference

- `make all` — format, lint, typecheck, test with coverage
- `make test` — run tests (parallel with pytest-xdist)
- `make lint` — ruff format check + ruff check
- `make typecheck` — pyright strict mode

## Code Rules

- No runtime dependencies (stdlib only)
- 100% test coverage required
- All implementation modules are private (`_tokenizer.py`, etc.)
- Public API is exported from `__init__.py`
- Tests are ported from the Handlebars.js spec suite — maintain 1:1 correspondence
- Single quotes for code, double quotes for docstrings
- Google-style docstrings
- Python 3.10+ (use `X | Y` union syntax in annotations, but `isinstance(x, (X, Y))` in runtime checks)
- No `except Exception` — catch specific types
- No imports inside functions

## Architecture

1. Tokenizer (`_tokenizer.py`) → Token stream
2. Parser (`_parser.py`) → AST (`_ast_nodes.py`)
3. Compiler (`_compiler.py`) → Output string

## Security

Templates may be untrusted. Block all dunder attribute access (`__class__`, `__dict__`, etc.) in path lookups. Enforce depth limits for nesting.

## Testing

Tests are ported from https://github.com/handlebars-lang/handlebars.js/tree/master/spec. When adding new features, find the corresponding JS spec tests and port them. Use `assert render(template, context) == expected` pattern. No test classes — standalone functions only.
