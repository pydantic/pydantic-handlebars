"""Utility functions and classes for pydantic_handlebars."""

from __future__ import annotations

from typing import Any

# HTML escape mapping matching Handlebars.js escapeExpression exactly
_ESCAPE_MAP: dict[str, str] = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#x27;',
    '`': '&#x60;',
    '=': '&#x3D;',
}


class SafeString(str):
    """A string subclass that marks content as safe (no HTML escaping).

    When a SafeString is rendered in a `{{expression}}` context, it will
    NOT be HTML-escaped, even though normal strings would be.
    """


def escape_expression(value: str) -> str:
    """Escape a string for safe inclusion in HTML.

    This matches the Handlebars.js `escapeExpression` function exactly.

    Args:
        value: The string to escape.

    Returns:
        The HTML-escaped string.
    """
    result: list[str] = []
    for char in value:
        if char in _ESCAPE_MAP:
            result.append(_ESCAPE_MAP[char])
        else:
            result.append(char)
    return ''.join(result)


def to_string(value: Any) -> str:
    """Convert a value to its string representation for template output.

    Matches Handlebars.js string coercion:
    - None/undefined → ""
    - True → "true"
    - False → "false"
    - Numbers → string representation
    - SafeString → preserved as-is

    Args:
        value: The value to convert.

    Returns:
        The string representation.
    """
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, SafeString):
        return str(value)
    return str(value)


def is_falsy(value: Any) -> bool:
    """Check if a value is falsy in Handlebars semantics.

    Falsy values: False, None, "", 0, [].
    Note: empty dict {} is TRUTHY in Handlebars.

    Args:
        value: The value to check.

    Returns:
        True if the value is falsy.
    """
    if value is None:
        return True
    if isinstance(value, bool):
        return not value
    if isinstance(value, str):
        return value == ''
    if isinstance(value, (int, float)):
        return value == 0
    if isinstance(value, list):
        return not value
    return False
