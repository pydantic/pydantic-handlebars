"""Handlebars template engine for composing LLM prompts, built on Pydantic."""

from __future__ import annotations

from importlib.metadata import version
from typing import Any, TypeVar, overload

from pydantic import TypeAdapter

from pydantic_handlebars._compiler import HelperFunc, HelperOptions
from pydantic_handlebars._environment import CompiledTemplate, HandlebarsEnvironment
from pydantic_handlebars._exceptions import (
    HandlebarsError,
    HandlebarsParseError,
    HandlebarsRuntimeError,
    TemplateSchemaError,
)
from pydantic_handlebars._pydantic import CompiledTypedTemplate, TypedCompiler
from pydantic_handlebars._schema import (
    CompatibilityResult,
    IssueSeverity,
    TemplateIssue,
    check_template_compatibility,
)
from pydantic_handlebars._utils import SafeString, escape_expression

T = TypeVar('T')

__version__ = version('pydantic-handlebars')

__all__ = [
    '__version__',
    'compile',
    'render',
    'typed_compiler',
    'SafeString',
    'HandlebarsError',
    'HandlebarsParseError',
    'HandlebarsRuntimeError',
    'TemplateSchemaError',
    'HandlebarsEnvironment',
    'CompiledTemplate',
    'CompiledTypedTemplate',
    'TypedCompiler',
    'HelperFunc',
    'HelperOptions',
    'escape_expression',
    'check_template_compatibility',
    'CompatibilityResult',
    'TemplateIssue',
    'IssueSeverity',
]

# Default environment for module-level functions
_default_env = HandlebarsEnvironment()


def render(source: str, context: dict[str, Any] | None = None) -> str:
    """Render a Handlebars template string with the given context.

    This is a convenience function that uses a default environment with
    standard Handlebars helpers registered.

    Args:
        source: The Handlebars template string.
        context: The data context for rendering.

    Returns:
        The rendered string.

    Example:
        ```python
        result = render('Hello {{name}}!', {'name': 'World'})
        assert result == 'Hello World!'
        ```
    """
    return _default_env.render(source, context if context is not None else {})


@overload
def compile(source: str) -> CompiledTemplate: ...  # pragma: no cover


@overload
def compile(
    source: str, tp: type[T], *, serialize_as_any: bool = ...
) -> CompiledTypedTemplate[T]: ...  # pragma: no cover


def compile(
    source: str, tp: type[Any] | None = None, *, serialize_as_any: bool = False
) -> CompiledTemplate | CompiledTypedTemplate[Any]:
    """Compile a Handlebars template string into a reusable callable.

    When called with just a source string, returns a ``CompiledTemplate``.
    When called with a source string and a type, validates the template against
    the type's JSON schema and returns a ``CompiledTypedTemplate``.

    Args:
        source: The Handlebars template string.
        tp: Optional Pydantic model type or any type supported by TypeAdapter.
        serialize_as_any: If True, serialize subclass fields instead of only
            the declared type's fields. Only applies when ``tp`` is provided.

    Returns:
        A ``CompiledTemplate`` or ``CompiledTypedTemplate`` callable.

    Example:
        ```python
        template = compile('Hello {{name}}!')
        result = template.render({'name': 'World'})
        assert result == 'Hello World!'
        ```
    """
    if tp is not None:
        type_adapter: TypeAdapter[Any] = TypeAdapter(tp)
        json_schema = type_adapter.json_schema(mode='serialization')
        helper_names = set(_default_env._helpers.keys())  # pyright: ignore[reportPrivateUsage]
        check_template_compatibility(source, json_schema, raise_on_error=True, helpers=helper_names)
        fn = _default_env._compile_fn(source)  # pyright: ignore[reportPrivateUsage]
        return CompiledTypedTemplate(fn=fn, type_adapter=type_adapter, serialize_as_any=serialize_as_any)
    return _default_env.compile(source)


def typed_compiler(
    tp: type[T],
    *,
    env: HandlebarsEnvironment | None = None,
    optional_field_severity: IssueSeverity = 'error',
    serialize_as_any: bool = False,
) -> TypedCompiler[T]:
    """Create a typed compiler for repeated compilation against a type.

    Args:
        tp: The Pydantic model type or any type supported by TypeAdapter.
        env: Optional HandlebarsEnvironment. Uses a default if not provided.
        optional_field_severity: Severity for optional field access issues.
        serialize_as_any: If True, serialize subclass fields instead of only
            the declared type's fields.

    Returns:
        A ``TypedCompiler`` instance.
    """
    return TypedCompiler(
        tp, env=env, optional_field_severity=optional_field_severity, serialize_as_any=serialize_as_any
    )
