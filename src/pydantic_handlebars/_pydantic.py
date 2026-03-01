"""Pydantic integration for typed template rendering."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Generic, TypeVar

from pydantic import TypeAdapter

from pydantic_handlebars._environment import HandlebarsEnvironment
from pydantic_handlebars._schema import IssueSeverity, check_template_compatibility

T = TypeVar('T')


class CompiledTypedTemplate(Generic[T]):
    """A compiled template bound to a specific type.

    Created by ``TypedCompiler.compile()`` or ``compile(source, tp)``.
    """

    def __init__(
        self,
        *,
        fn: Callable[..., str],
        type_adapter: TypeAdapter[T],
        serialize_as_any: bool = False,
    ) -> None:
        self._fn = fn
        self._type_adapter = type_adapter
        self._serialize_as_any = serialize_as_any

    def render(self, data: T) -> str:
        """Render with typed data (no runtime validation).

        Args:
            data: The data to render. Must match type T.

        Returns:
            The rendered template string.
        """
        context = self._type_adapter.dump_python(data, mode='json', serialize_as_any=self._serialize_as_any)
        return self._fn(context)

    def validate_and_render(self, data: Any) -> str:
        """Validate data through Pydantic, then render.

        Args:
            data: The data to validate and render. Can be any type that
                Pydantic can coerce to T.

        Returns:
            The rendered template string.
        """
        validated = self._type_adapter.validate_python(data)
        context = self._type_adapter.dump_python(validated, mode='json', serialize_as_any=self._serialize_as_any)
        return self._fn(context)


class TypedCompiler(Generic[T]):
    """Compiler for creating typed templates against a Pydantic model.

    Caches the TypeAdapter and JSON schema for repeated compilation against
    the same type.

    Args:
        tp: The Pydantic model type or any type supported by TypeAdapter.
        env: Optional HandlebarsEnvironment. Uses a default if not provided.
        optional_field_severity: Severity for optional field access issues.

    Example:
        ```python
        from pydantic import BaseModel

        class User(BaseModel):
            name: str
            age: int

        compiler = TypedCompiler(User)
        template = compiler.compile('Hello {{name}}, you are {{age}}!')
        result = template.render(User(name='Alice', age=30))
        assert result == 'Hello Alice, you are 30!'
        ```
    """

    def __init__(
        self,
        tp: type[T],
        *,
        env: HandlebarsEnvironment | None = None,
        optional_field_severity: IssueSeverity = 'error',
        serialize_as_any: bool = False,
    ) -> None:
        self._type_adapter: TypeAdapter[T] = TypeAdapter(tp)
        self._json_schema = self._type_adapter.json_schema(mode='serialization')
        self._env = env or HandlebarsEnvironment()
        self._optional_field_severity: IssueSeverity = optional_field_severity
        self._serialize_as_any = serialize_as_any

    @property
    def json_schema(self) -> dict[str, Any]:
        """The JSON schema derived from the type."""
        return self._json_schema

    def compile(self, source: str, *, raise_on_error: bool = True) -> CompiledTypedTemplate[T]:
        """Compile a template, checking compatibility with the schema.

        Args:
            source: The Handlebars template string.
            raise_on_error: If True (default), raise on incompatible templates.

        Returns:
            A ``CompiledTypedTemplate`` ready for rendering.

        Raises:
            TemplateSchemaError: If the template references fields not in the schema.
        """
        helper_names = set(self._env._helpers.keys())  # pyright: ignore[reportPrivateUsage]
        check_template_compatibility(
            source,
            self._json_schema,
            raise_on_error=raise_on_error,
            optional_field_severity=self._optional_field_severity,
            helpers=helper_names,
        )
        fn = self._env._compile_fn(source)  # pyright: ignore[reportPrivateUsage]
        return CompiledTypedTemplate(fn=fn, type_adapter=self._type_adapter, serialize_as_any=self._serialize_as_any)
