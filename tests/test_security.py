"""Tests for security features.

Ported from handlebars.js spec/security.js, adapted for Python.
"""

from datetime import datetime

import pytest

from pydantic_handlebars import HandlebarsRuntimeError, render

# --- Dunder keys in dicts are now normal keys (serialization makes them safe) ---


def test_dunder_class_key_renders():
    assert render('{{__class__}}', {'__class__': 'hacked'}) == 'hacked'


def test_dunder_dict_key_renders():
    assert render('{{obj.__dict__}}', {'obj': {'__dict__': 'hacked'}}) == 'hacked'


def test_dunder_globals_key_renders():
    assert render('{{__globals__}}', {'__globals__': 'hacked'}) == 'hacked'


def test_dunder_init_key_renders():
    assert render('{{obj.__init__}}', {'obj': {'__init__': 'hacked'}}) == 'hacked'


def test_dunder_module_key_renders():
    assert render('{{__module__}}', {'__module__': 'hacked'}) == 'hacked'


def test_dunder_subclasses_key_renders():
    assert render('{{__subclasses__}}', {'__subclasses__': 'hacked'}) == 'hacked'


def test_constructor_key_renders():
    assert render('{{constructor}}', {'constructor': 'hacked'}) == 'hacked'


def test_dunder_bases_key_renders():
    assert render('{{obj.__bases__}}', {'obj': {'__bases__': 'hacked'}}) == 'hacked'


def test_dunder_reduce_key_renders():
    assert render('{{obj.__reduce__}}', {'obj': {'__reduce__': 'hacked'}}) == 'hacked'


def test_dunder_code_key_renders():
    assert render('{{obj.__code__}}', {'obj': {'__code__': 'hacked'}}) == 'hacked'


def test_dunder_builtins_key_renders():
    assert render('{{__builtins__}}', {'__builtins__': 'hacked'}) == 'hacked'


def test_dunder_via_each():
    """Dunder keys render normally in each loops."""
    assert render('{{#each items}}{{__class__}}{{/each}}', {'items': [{'__class__': 'ok'}]}) == 'ok'


# --- Serialization tests ---


def test_datetime_serialized():
    """datetime objects are serialized to ISO format strings."""
    dt = datetime(2024, 1, 15, 10, 30, 0)
    result = render('{{date}}', {'date': dt})
    assert '2024-01-15' in result


def test_callable_in_context_raises():
    """Callables in context raise serialization errors."""
    with pytest.raises(HandlebarsRuntimeError, match='Context serialization failed'):
        render('{{fn}}', {'fn': lambda: True})


def test_arbitrary_object_in_context_raises():
    """Arbitrary non-serializable objects raise serialization errors."""

    class Obj:
        name = 'safe'

    with pytest.raises(HandlebarsRuntimeError, match='Context serialization failed'):
        render('{{obj.name}}', {'obj': Obj()})


def test_nested_serialization():
    """Nested dicts with serializable values work."""
    result = render('{{obj.date}}', {'obj': {'date': datetime(2024, 1, 15)}})
    assert '2024-01-15' in result


# --- HTML escaping ---


def test_html_not_escaped_by_default():
    """HTML in values is not escaped by default (auto_escape=False)."""
    assert render('{{val}}', {'val': '<script>alert(1)</script>'}) == '<script>alert(1)</script>'


def test_html_injection_escaped_when_enabled():
    """HTML in values is escaped when auto_escape=True."""
    from pydantic_handlebars import HandlebarsEnvironment

    env = HandlebarsEnvironment(auto_escape=True)
    assert env.render('{{val}}', {'val': '<script>alert(1)</script>'}) == '&lt;script&gt;alert(1)&lt;/script&gt;'


def test_html_injection_not_escaped_with_triple():
    assert render('{{{val}}}', {'val': '<script>alert(1)</script>'}) == '<script>alert(1)</script>'
