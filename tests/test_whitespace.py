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
