"""HandlebarsEnvironment class for managing helpers and rendering."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar, overload

from pydantic_core import to_jsonable_python

from pydantic_handlebars._compiler import MAX_DEPTH, MAX_OUTPUT_SIZE, Compiler, HelperFunc
from pydantic_handlebars._exceptions import HandlebarsRuntimeError
from pydantic_handlebars._helpers import get_extra_helpers, get_standard_helpers
from pydantic_handlebars._parser import parse

F = TypeVar('F', bound=Callable[..., Any])


class CompiledTemplate:
    """A compiled Handlebars template."""

    def __init__(self, fn: Callable[..., str]) -> None:
        self._fn = fn

    def render(self, context: dict[str, Any] | None = None) -> str:
        """Render the template with the given context."""
        ctx = context if context is not None else {}
        try:
            serialized = to_jsonable_python(ctx)
        except ValueError as e:
            raise HandlebarsRuntimeError(f'Context serialization failed: {e}') from e
        return self._fn(serialized)


class HandlebarsEnvironment:
    """An environment for rendering Handlebars templates with custom helpers.

    The environment manages a set of helpers (both built-in and user-registered)
    and provides methods for compiling and rendering templates.

    Example:
        ```python
        env = HandlebarsEnvironment()


        @env.helper
        def shout(*args: object, options: HelperOptions) -> str:
            return str(args[0]).upper() + '!!!'


        result = env.render('{{shout name}}', {'name': 'world'})
        assert result == 'WORLD!!!'
        ```
    """

    def __init__(
        self,
        *,
        extra_helpers: bool = False,
        auto_escape: bool = False,
        max_depth: int = MAX_DEPTH,
        max_output_size: int = MAX_OUTPUT_SIZE,
    ) -> None:
        self._helpers: dict[str, HelperFunc] = get_standard_helpers()
        if extra_helpers:
            self._helpers.update(get_extra_helpers())
        self._auto_escape = auto_escape
        self._max_depth = max_depth
        self._max_output_size = max_output_size

    @property
    def auto_escape(self) -> bool:
        """Whether HTML auto-escaping is enabled for ``{{expression}}`` output.

        When ``False`` (the default), no escaping is applied — appropriate for
        non-HTML use cases like prompt generation.  When ``True``,
        double-stache expressions are HTML-escaped.  Triple-stache
        ``{{{expression}}}`` is always unescaped regardless of this setting.
        """
        return self._auto_escape

    @overload
    def helper(self, fn: F) -> F: ...  # pragma: no cover

    @overload
    def helper(self, fn: str) -> Callable[[F], F]: ...  # pragma: no cover

    def helper(self, fn: F | str) -> F | Callable[[F], F]:
        """Register a helper function.

        Can be used as a decorator (with or without a name argument):

        ```python
        @env.helper
        def my_helper(*args: object, options: HelperOptions) -> str:
            return str(args[0]).upper()


        @env.helper('custom-name')
        def my_helper(*args: object, options: HelperOptions) -> str:
            return str(args[0]).upper()
        ```

        Args:
            fn: The helper function, or a name string for use as a decorator factory.

        Returns:
            The registered function, or a decorator.
        """
        if isinstance(fn, str):
            name = fn

            def decorator(func: F) -> F:
                self._helpers[name] = func
                return func

            return decorator
        else:
            self._helpers[fn.__name__] = fn
            return fn

    def register_helper(self, name: str, fn: HelperFunc) -> None:
        """Register a helper function with an explicit name.

        Args:
            name: The name to register the helper under.
            fn: The helper function.
        """
        self._helpers[name] = fn

    def unregister_helper(self, name: str) -> None:
        """Unregister a helper by name.

        Args:
            name: The name of the helper to remove.

        Raises:
            KeyError: If the helper is not registered.
        """
        if name not in self._helpers:
            raise KeyError(f'Helper not found: {name}')
        del self._helpers[name]

    def _compile_fn(self, source: str) -> Callable[..., str]:
        """Compile to a raw callable (internal use)."""
        program = parse(source)
        helpers = dict(self._helpers)
        auto_escape = self._auto_escape
        max_depth = self._max_depth
        max_output_size = self._max_output_size

        def template(context: Any = None) -> str:
            ctx: Any = context if context is not None else {}
            compiler = Compiler(
                helpers=helpers,
                auto_escape=auto_escape,
                max_depth=max_depth,
                max_output_size=max_output_size,
            )
            return compiler.render(program, ctx)

        return template

    def compile(self, source: str) -> CompiledTemplate:
        """Compile a template string into a reusable callable.

        Args:
            source: The Handlebars template string.

        Returns:
            A ``CompiledTemplate`` that takes a context dict and returns a rendered string.
        """
        return CompiledTemplate(self._compile_fn(source))

    def render(self, source: str, context: Any = None) -> str:
        """Render a template string with the given context.

        Args:
            source: The Handlebars template string.
            context: The data context for rendering.

        Returns:
            The rendered string.
        """
        template = self.compile(source)
        return template.render(context if context is not None else {})
