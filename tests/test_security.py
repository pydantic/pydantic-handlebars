"""Tests for security features.

Ported from handlebars.js spec/security.js, adapted for Python.
"""

from pydantic_handlebars import render


def test_block_dunder_class():
    assert render('{{__class__}}', {'__class__': 'hacked'}) == ''


def test_block_dunder_dict():
    assert render('{{obj.__dict__}}', {'obj': {'__dict__': 'hacked'}}) == ''


def test_block_dunder_globals():
    assert render('{{__globals__}}', {'__globals__': 'hacked'}) == ''


def test_block_dunder_init():
    assert render('{{obj.__init__}}', {'obj': {'__init__': 'hacked'}}) == ''


def test_block_dunder_module():
    assert render('{{__module__}}', {'__module__': 'hacked'}) == ''


def test_block_dunder_subclasses():
    assert render('{{__subclasses__}}', {'__subclasses__': 'hacked'}) == ''


def test_block_constructor():
    assert render('{{constructor}}', {'constructor': 'hacked'}) == ''


def test_block_dunder_in_path():
    assert render('{{obj.__class__}}', {'obj': object()}) == ''


def test_block_dunder_nested():
    assert render('{{a.__class__.__bases__}}', {'a': 'hello'}) == ''


def test_block_dunder_via_each():
    """Ensure dunder access is blocked even in each loops."""
    assert render('{{#each items}}{{__class__}}{{/each}}', {'items': [1, 2]}) == ''


def test_safe_attribute_access():
    """Non-dunder attributes should still work."""

    class Obj:
        name = 'safe'

    assert render('{{obj.name}}', {'obj': Obj()}) == 'safe'


def test_block_dunder_bases():
    assert render('{{obj.__bases__}}', {'obj': {'__bases__': 'hacked'}}) == ''


def test_block_dunder_reduce():
    assert render('{{obj.__reduce__}}', {'obj': {'__reduce__': 'hacked'}}) == ''


def test_block_dunder_code():
    assert render('{{obj.__code__}}', {'obj': {'__code__': 'hacked'}}) == ''


def test_block_dunder_builtins():
    assert render('{{__builtins__}}', {'__builtins__': 'hacked'}) == ''


def test_html_injection_escaped_by_default():
    """HTML in values is escaped by default."""
    assert render('{{val}}', {'val': '<script>alert(1)</script>'}) == '&lt;script&gt;alert(1)&lt;/script&gt;'


def test_html_injection_not_escaped_with_triple():
    assert render('{{{val}}}', {'val': '<script>alert(1)</script>'}) == '<script>alert(1)</script>'
