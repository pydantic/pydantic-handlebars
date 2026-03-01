"""Regression tests.

Ported from handlebars.js spec/regressions.js (relevant parts).
"""

# pyright: reportUnknownLambdaType=false, reportUnknownArgumentType=false

from pydantic_handlebars import HandlebarsEnvironment, render


def test_rendering_undefined_doesnt_crash():
    assert render('{{foo}}', {}) == ''


def test_rendering_null_doesnt_crash():
    assert render('{{foo}}', {'foo': None}) == ''


def test_if_with_empty_dict_is_truthy():
    """Empty dict should be truthy in Handlebars."""
    assert render('{{#if obj}}yes{{else}}no{{/if}}', {'obj': {}}) == 'yes'


def test_nested_undefined_path_doesnt_crash():
    assert render('{{foo.bar.baz}}', {}) == ''
    assert render('{{foo.bar.baz}}', {'foo': {}}) == ''
    assert render('{{foo.bar.baz}}', {'foo': {'bar': {}}}) == ''


def test_each_with_string_context():
    """Each should handle non-iterable gracefully."""
    assert render('{{#each val}}x{{else}}empty{{/each}}', {'val': 'string'}) == 'empty'


def test_with_false_context():
    """With should show else for falsy values."""
    assert render('{{#with val}}yes{{else}}no{{/with}}', {'val': False}) == 'no'
    assert render('{{#with val}}yes{{else}}no{{/with}}', {'val': None}) == 'no'
    assert render('{{#with val}}yes{{else}}no{{/with}}', {'val': ''}) == 'no'
    assert render('{{#with val}}yes{{else}}no{{/with}}', {'val': 0}) == 'no'


def test_if_with_dict_is_truthy():
    assert render('{{#if val}}yes{{else}}no{{/if}}', {'val': {'key': 'value'}}) == 'yes'


def test_multiple_comments():
    assert render('{{! one }}{{! two }}hello', {}) == 'hello'


def test_comment_inside_content():
    assert render('before{{! comment }}after', {}) == 'beforeafter'


def test_each_empty_body():
    assert render('{{#each items}}{{/each}}', {'items': [1, 2, 3]}) == ''


def test_nested_each_with_parent_context():
    template = '{{#each items}}{{#each sub}}{{../../name}}{{/each}}{{/each}}'
    data = {'items': [{'sub': [1]}], 'name': 'root'}
    assert render(template, data) == 'root'


def test_helper_with_string_arg():
    env = HandlebarsEnvironment()
    env.register_helper('echo', lambda *args, **kw: str(args[0]) if args else '')
    assert env.render('{{echo "hello world"}}', {}) == 'hello world'


def test_block_with_numeric_path_segment():
    """Closing block tag should accept NUMBER tokens in dot-notation paths."""
    template = '{{#items.0}}{{name}}{{/items.0}}'
    data = {'items': [{'name': 'first'}]}
    assert render(template, data) == 'first'


def test_block_with_slash_separator():
    """Closing block tag should preserve slash separators in path matching."""
    template = '{{#a/b}}{{c}}{{/a/b}}'
    data = {'a': {'b': {'c': 'yes'}}}
    assert render(template, data) == 'yes'


def test_block_with_slash_numeric_path():
    """Closing block tag should handle slash separators with numeric segments."""
    template = '{{#items/0}}{{name}}{{/items/0}}'
    data = {'items': [{'name': 'first'}]}
    assert render(template, data) == 'first'


def test_whitespace_in_expressions():
    assert render('{{  foo  }}', {'foo': 'bar'}) == 'bar'


def test_newline_in_expression():
    assert render('{{\nfoo\n}}', {'foo': 'bar'}) == 'bar'
