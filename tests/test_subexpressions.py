"""Tests for subexpressions.

Ported from handlebars.js spec/subexpressions.js.
"""

# pyright: reportUnknownLambdaType=false, reportUnknownArgumentType=false, reportArgumentType=false

from pydantic_handlebars import HandlebarsEnvironment, HelperOptions, SafeString

_extra_env = HandlebarsEnvironment(extra_helpers=True)


def test_subexpression_as_arg():
    env = HandlebarsEnvironment()
    env.register_helper('loud', lambda *args, **kw: str(args[0]).upper() if args else '')
    env.register_helper('echo', lambda *args, **kw: str(args[0]) if args else '')
    assert env.render('{{echo (loud "hello")}}', {}) == 'HELLO'


def test_nested_subexpressions():
    env = HandlebarsEnvironment()
    env.register_helper('add', lambda *args, **kw: str(int(args[0]) + int(args[1])) if len(args) >= 2 else '')
    assert env.render('{{add (add 1 2) 3}}', {}) == '6'


def test_subexpression_with_context():
    env = HandlebarsEnvironment()
    env.register_helper('loud', lambda *args, **kw: str(args[0]).upper() if args else '')
    assert env.render('{{loud (lookup person "name")}}', {'person': {'name': 'Alice'}}) == 'ALICE'


def test_subexpression_in_hash():
    env = HandlebarsEnvironment()

    def link(*args: object, options: HelperOptions) -> SafeString:
        url = options.hash.get('url', '#')
        text = options.hash.get('text', '')
        return SafeString(f'<a href="{url}">{text}</a>')

    env.register_helper('link', link)
    env.register_helper('loud', lambda *args, **kw: str(args[0]).upper() if args else '')
    assert (
        env.render('{{link text=(loud "click") url="http://example.com"}}', {})
        == '<a href="http://example.com">CLICK</a>'
    )


def test_subexpression_with_boolean_helpers():
    """Test subexpressions with eq/ne comparisons inside #if."""
    assert _extra_env.render('{{#if (eq a b)}}equal{{else}}not equal{{/if}}', {'a': 1, 'b': 1}) == 'equal'
    assert _extra_env.render('{{#if (eq a b)}}equal{{else}}not equal{{/if}}', {'a': 1, 'b': 2}) == 'not equal'


def test_subexpression_with_and_or():
    assert _extra_env.render('{{#if (and a b)}}yes{{else}}no{{/if}}', {'a': True, 'b': True}) == 'yes'
    assert _extra_env.render('{{#if (and a b)}}yes{{else}}no{{/if}}', {'a': True, 'b': False}) == 'no'
    assert _extra_env.render('{{#if (or a b)}}yes{{else}}no{{/if}}', {'a': False, 'b': True}) == 'yes'
    assert _extra_env.render('{{#if (or a b)}}yes{{else}}no{{/if}}', {'a': False, 'b': False}) == 'no'


def test_subexpression_with_not():
    assert _extra_env.render('{{#if (not a)}}yes{{else}}no{{/if}}', {'a': False}) == 'yes'
    assert _extra_env.render('{{#if (not a)}}yes{{else}}no{{/if}}', {'a': True}) == 'no'
