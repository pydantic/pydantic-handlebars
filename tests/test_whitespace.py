"""Tests for whitespace control.

Ported from handlebars.js spec/whitespace-control.js.
"""

from pydantic_handlebars import render


def test_strip_whitespace_before_mustache():
    assert render('  {{~foo}}', {'foo': 'bar'}) == 'bar'


def test_strip_whitespace_after_mustache():
    assert render('{{foo~}}  ', {'foo': 'bar'}) == 'bar'


def test_strip_whitespace_both_sides():
    assert render('  {{~foo~}}  ', {'foo': 'bar'}) == 'bar'


def test_strip_with_newlines():
    assert render('foo\n  {{~bar}}\n  baz', {'bar': 'BAR'}) == 'fooBAR\n  baz'


def test_strip_after_with_newlines():
    assert render('foo\n  {{bar~}}\n  baz', {'bar': 'BAR'}) == 'foo\n  BARbaz'


def test_strip_both_with_newlines():
    assert render('foo\n  {{~bar~}}\n  baz', {'bar': 'BAR'}) == 'fooBARbaz'


def test_strip_block_open():
    template = '  {{~#if show~}}  \ncontent\n  {{~/if~}}  '
    assert render(template, {'show': True}) == 'content'


def test_no_strip():
    assert render('  {{foo}}  ', {'foo': 'bar'}) == '  bar  '


# --- Comment whitespace control ---


def test_comment_strip_open():
    """{{~! comment }} strips preceding whitespace."""
    assert render('  {{~! comment }}after', {}) == 'after'


def test_comment_strip_close():
    """{{! comment ~}} strips following whitespace."""
    assert render('before{{! comment ~}}  ', {}) == 'before'


def test_comment_strip_both():
    """{{~! comment ~}} strips whitespace on both sides."""
    assert render('  {{~! comment ~}}  ', {}) == ''


def test_long_comment_strip_open():
    """{{~!-- comment --}} strips preceding whitespace."""
    assert render('  {{~!-- comment --}}after', {}) == 'after'


def test_long_comment_strip_close():
    """{{!-- comment --~}} strips following whitespace."""
    assert render('before{{!-- comment --~}}  ', {}) == 'before'


def test_long_comment_strip_both():
    """{{~!-- comment --~}} strips whitespace on both sides."""
    assert render('  {{~!-- comment --~}}  ', {}) == ''


def test_comment_strip_with_newlines():
    """Comment strip markers remove newlines and surrounding whitespace."""
    assert render('foo\n  {{~! comment ~}}\n  bar', {}) == 'foobar'


def test_long_comment_strip_with_newlines():
    """Long comment strip markers remove newlines and surrounding whitespace."""
    assert render('foo\n  {{~!-- comment --~}}\n  bar', {}) == 'foobar'


# --- Else/inverse whitespace control ---


def test_else_strip_open():
    """{{~else}} strips trailing whitespace from body."""
    assert render('{{#if show}} body {{~else}} other {{/if}}', {'show': True}) == ' body'
    assert render('{{#if show}} body {{~else}} other {{/if}}', {'show': False}) == ' other '


def test_else_strip_close():
    """{{else~}} strips leading whitespace from inverse."""
    assert render('{{#if show}} body {{else~}} other {{/if}}', {'show': True}) == ' body '
    assert render('{{#if show}} body {{else~}} other {{/if}}', {'show': False}) == 'other '


def test_else_strip_both():
    """{{~else~}} strips trailing ws from body and leading ws from inverse."""
    assert render('{{#if show}} body {{~else~}} other {{/if}}', {'show': True}) == ' body'
    assert render('{{#if show}} body {{~else~}} other {{/if}}', {'show': False}) == 'other '


def test_caret_strip_open():
    """{{~^}} strips trailing whitespace from body."""
    assert render('{{#if show}} body {{~^}} other {{/if}}', {'show': True}) == ' body'
    assert render('{{#if show}} body {{~^}} other {{/if}}', {'show': False}) == ' other '


def test_caret_strip_close():
    """{{^~}} strips leading whitespace from inverse."""
    assert render('{{#if show}} body {{^~}} other {{/if}}', {'show': True}) == ' body '
    assert render('{{#if show}} body {{^~}} other {{/if}}', {'show': False}) == 'other '


def test_caret_strip_both():
    """{{~^~}} strips both sides."""
    assert render('{{#if show}} body {{~^~}} other {{/if}}', {'show': True}) == ' body'
    assert render('{{#if show}} body {{~^~}} other {{/if}}', {'show': False}) == 'other '


def test_else_strip_with_close_strip():
    """Combine {{~else~}} with {{~/if}} for full control."""
    assert render('{{#if show}} body {{~else~}} other {{~/if}}', {'show': False}) == 'other'


def test_else_strip_with_newlines():
    """Else strip markers work across newlines."""
    template = '{{#if show}}\n  body\n  {{~else~}}\n  other\n{{/if}}'
    assert render(template, {'show': True}) == '\n  body'
    assert render(template, {'show': False}) == 'other\n'


# --- Context-based block inner whitespace control ---


def test_context_block_inner_strip():
    """{{#name~}} and {{~/name}} strip inner whitespace for context blocks."""
    assert render('{{#name~}} hi {{~/name}}', {'name': 'World'}) == 'hi'


def test_context_block_inner_strip_open_only():
    """{{#name~}} strips leading whitespace from body."""
    assert render('{{#name~}} hi {{/name}}', {'name': 'World'}) == 'hi '


def test_context_block_inner_strip_close_only():
    """{{~/name}} strips trailing whitespace from body."""
    assert render('{{#name}} hi {{~/name}}', {'name': 'World'}) == ' hi'


def test_context_block_inverse_strip():
    """Whitespace control on else for context-based blocks."""
    assert render('{{#val}} yes {{~else~}} no {{/val}}', {'val': ''}) == 'no '
    assert render('{{#val}} yes {{~else~}} no {{/val}}', {'val': 'x'}) == ' yes'


def test_context_block_list_inner_strip():
    """Inner strip works for context blocks that iterate lists."""
    assert render('{{#items~}} x {{~/items}}', {'items': [1, 2]}) == 'x  x'
