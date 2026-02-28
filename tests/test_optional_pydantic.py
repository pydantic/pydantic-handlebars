"""Tests that verify clear ImportError messages when pydantic features are used without pydantic."""

import importlib.util

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec('pydantic') is not None,
    reason='Test only runs when pydantic is NOT installed',
)


def test_import_compiled_typed_template():
    with pytest.raises(ImportError, match='requires pydantic'):
        from pydantic_handlebars import CompiledTypedTemplate

        _ = CompiledTypedTemplate


def test_import_typed_compiler():
    with pytest.raises(ImportError, match='requires pydantic'):
        from pydantic_handlebars import TypedCompiler

        _ = TypedCompiler


def test_compile_with_type():
    from pydantic_handlebars import compile

    with pytest.raises(ImportError, match='requires pydantic'):
        compile('{{name}}', dict)


def test_typed_compiler():
    from pydantic_handlebars import typed_compiler

    with pytest.raises(ImportError, match='requires pydantic'):
        typed_compiler(dict)
