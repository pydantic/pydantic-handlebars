"""Exception hierarchy for pydantic_handlebars."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic_handlebars._schema import CompatibilityResult


class HandlebarsError(Exception):
    """Base exception for all Handlebars errors."""


class HandlebarsParseError(HandlebarsError):
    """Raised when a template cannot be parsed.

    Attributes:
        message: The error message.
        line: The line number where the error occurred (1-based).
        column: The column number where the error occurred (1-based).
    """

    def __init__(self, message: str, *, line: int | None = None, column: int | None = None) -> None:
        self.line = line
        self.column = column
        if line is not None and column is not None:
            full_message = f'{message} at line {line}, column {column}'
        elif line is not None:
            full_message = f'{message} at line {line}'
        else:
            full_message = message
        super().__init__(full_message)


class HandlebarsRuntimeError(HandlebarsError):
    """Raised when an error occurs during template rendering."""


class TemplateSchemaError(HandlebarsError):
    """Raised when templates are incompatible with the provided JSON schema."""

    def __init__(self, message: str, *, result: CompatibilityResult) -> None:
        self.result = result
        super().__init__(message)
