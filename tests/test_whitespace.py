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
