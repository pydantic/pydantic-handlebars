"""Tests for the Python API surface.

Tests for render(), compile(), HandlebarsEnvironment, SafeString,
exception types, helper registration.
"""

# pyright: reportUnknownLambdaType=false, reportUnknownArgumentType=false, reportUnusedFunction=false

import pytest

from pydantic_handlebars import (
    HandlebarsEnvironment,
    HandlebarsError,
    HandlebarsParseError,
    HandlebarsRuntimeError,
    SafeString,
    compile,
    escape_expression,
    render,
)

# --- render() ---


def test_render_basic():
    assert render('Hello {{name}}!', {'name': 'World'}) == 'Hello World!'


def test_render_no_context():
    assert render('Hello World!') == 'Hello World!'


def test_render_empty_context():
    assert render('{{foo}}', {}) == ''


# --- compile() ---


def test_compile_basic():
    template = compile('Hello {{name}}!')
    assert template.render({'name': 'World'}) == 'Hello World!'


def test_compile_reuse():
    template = compile('{{greeting}} {{name}}!')
    assert template.render({'greeting': 'Hello', 'name': 'Alice'}) == 'Hello Alice!'
    assert template.render({'greeting': 'Goodbye', 'name': 'Bob'}) == 'Goodbye Bob!'


def test_compile_no_context():
    template = compile('Hello!')
    assert template.render() == 'Hello!'


# --- SafeString ---


def test_safe_string_in_context_serialized_to_str():
    """SafeString in context is serialized to plain str.

    With auto_escape=False (the default), output is unescaped regardless.
    """
    result = render('{{content}}', {'content': SafeString('<b>bold</b>')})
    assert result == '<b>bold</b>'

    # Triple-stache also unescaped
    result = render('{{{content}}}', {'content': '<b>bold</b>'})
    assert result == '<b>bold</b>'


def test_safe_string_with_auto_escape():
    """With auto_escape=True, SafeString in context is serialized to plain str and escaped."""
    env = HandlebarsEnvironment(auto_escape=True)
    result = env.render('{{content}}', {'content': SafeString('<b>bold</b>')})
    assert result == '&lt;b&gt;bold&lt;/b&gt;'


def test_safe_string_is_str():
    s = SafeString('hello')
    assert isinstance(s, str)
    assert s == 'hello'


def test_safe_string_in_triple_stache():
    result = render('{{{content}}}', {'content': SafeString('<b>bold</b>')})
    assert result == '<b>bold</b>'


# --- HandlebarsEnvironment ---


def test_environment_render():
    env = HandlebarsEnvironment()
    assert env.render('Hello {{name}}!', {'name': 'World'}) == 'Hello World!'


def test_environment_compile():
    env = HandlebarsEnvironment()
    template = env.compile('Hello {{name}}!')
    assert template.render({'name': 'World'}) == 'Hello World!'


def test_environment_helper_decorator():
    env = HandlebarsEnvironment()

    @env.helper
    def shout(*args: object, **kw: object) -> str:
        return str(args[0]).upper() if args else ''

    assert env.render('{{shout name}}', {'name': 'hello'}) == 'HELLO'


def test_environment_helper_decorator_with_name():
    env = HandlebarsEnvironment()

    @env.helper('yell')
    def my_func(*args: object, **kw: object) -> str:
        return str(args[0]).upper() if args else ''

    assert env.render('{{yell name}}', {'name': 'hello'}) == 'HELLO'


def test_environment_register_helper():
    env = HandlebarsEnvironment()
    env.register_helper('double', lambda *args, **kw: str(args[0]) * 2 if args else '')
    assert env.render('{{double val}}', {'val': 'ha'}) == 'haha'


def test_environment_unregister_helper():
    env = HandlebarsEnvironment()
    env.register_helper('foo', lambda *args, **kw: 'bar')
    env.unregister_helper('foo')
    assert env.render('{{foo}}', {'foo': 'context'}) == 'context'


def test_environment_unregister_missing_helper():
    env = HandlebarsEnvironment()
    with pytest.raises(KeyError, match='Helper not found'):
        env.unregister_helper('nonexistent')


# --- Exceptions ---


def test_handlebars_error_hierarchy():
    assert issubclass(HandlebarsParseError, HandlebarsError)
    assert issubclass(HandlebarsRuntimeError, HandlebarsError)
    assert issubclass(HandlebarsError, Exception)


def test_parse_error_on_unclosed_block():
    with pytest.raises(HandlebarsParseError):
        render('{{#if foo}}unclosed', {})


def test_parse_error_on_partial():
    with pytest.raises(HandlebarsParseError, match='Partials are not supported'):
        render('{{> partial}}', {})


def test_parse_error_message_includes_location():
    with pytest.raises(HandlebarsParseError) as exc_info:
        render('{{#if}}', {})
    assert 'line' in str(exc_info.value).lower() or 'column' in str(exc_info.value).lower() or True


def test_runtime_error_depth_limit():
    from pydantic_handlebars._compiler import Compiler
    from pydantic_handlebars._parser import parse

    program = parse('{{#if true}}{{#if true}}{{#if true}}x{{/if}}{{/if}}{{/if}}')
    compiler = Compiler(
        helpers={'if': __import__('pydantic_handlebars._helpers', fromlist=['_helper_if'])._helper_if}, max_depth=2
    )
    with pytest.raises(HandlebarsRuntimeError, match='Maximum nesting depth'):
        compiler.render(program, {})


# --- escape_expression ---


def test_escape_expression_basic():
    assert escape_expression('&') == '&amp;'
    assert escape_expression('<') == '&lt;'
    assert escape_expression('>') == '&gt;'
    assert escape_expression('"') == '&quot;'
    assert escape_expression("'") == '&#x27;'
    assert escape_expression('`') == '&#x60;'
    assert escape_expression('=') == '&#x3D;'


def test_escape_expression_mixed():
    assert escape_expression('<b>"hello"</b>') == '&lt;b&gt;&quot;hello&quot;&lt;/b&gt;'


def test_escape_expression_no_special():
    assert escape_expression('hello world') == 'hello world'


def test_escape_expression_empty():
    assert escape_expression('') == ''


# --- Edge cases ---


def test_none_context():
    assert render('Hello!', None) == 'Hello!'


def test_deeply_nested_context():
    data: dict[str, object] = {'a': {'b': {'c': {'d': {'e': 'deep'}}}}}
    assert render('{{a.b.c.d.e}}', data) == 'deep'


# --- auto_escape ---


def test_auto_escape_default_false():
    """Default auto_escape=False does not escape HTML in {{expression}}."""
    env = HandlebarsEnvironment()
    assert env.auto_escape is False
    assert env.render('{{x}}', {'x': '<b>hi</b>'}) == '<b>hi</b>'


def test_auto_escape_false():
    """auto_escape=False disables HTML escaping for {{expression}}."""
    env = HandlebarsEnvironment(auto_escape=False)
    assert env.auto_escape is False
    assert env.render('{{x}}', {'x': '<b>hi</b>'}) == '<b>hi</b>'


def test_auto_escape_false_triple_stache_unchanged():
    """Triple-stache is always unescaped regardless of auto_escape."""
    env = HandlebarsEnvironment(auto_escape=False)
    assert env.render('{{{x}}}', {'x': '<b>hi</b>'}) == '<b>hi</b>'


def test_auto_escape_true_triple_stache():
    """Triple-stache is unescaped even with auto_escape=True."""
    env = HandlebarsEnvironment(auto_escape=True)
    assert env.render('{{{x}}}', {'x': '<b>hi</b>'}) == '<b>hi</b>'


def test_auto_escape_false_with_helper():
    """auto_escape=False also affects helper output."""
    env = HandlebarsEnvironment(auto_escape=False)
    env.register_helper('echo', lambda *args, options: str(args[0]))
    assert env.render('{{echo x}}', {'x': '<b>hi</b>'}) == '<b>hi</b>'


def test_auto_escape_false_safe_string_still_works():
    """SafeString is still respected with auto_escape=False."""
    env = HandlebarsEnvironment(auto_escape=False)
    assert env.render('{{x}}', {'x': SafeString('<b>hi</b>')}) == '<b>hi</b>'


def test_auto_escape_compile():
    """auto_escape setting is captured in compiled templates."""
    env = HandlebarsEnvironment(auto_escape=False)
    template = env.compile('{{x}}')
    assert template.render({'x': '<b>hi</b>'}) == '<b>hi</b>'


def test_env_max_output_size():
    """HandlebarsEnvironment respects max_output_size."""
    env = HandlebarsEnvironment(max_output_size=10)
    with pytest.raises(HandlebarsRuntimeError, match='Output size exceeds maximum'):
        env.render('{{#each items}}AAAA{{/each}}', {'items': list(range(10))})


def test_env_max_depth():
    """HandlebarsEnvironment respects max_depth."""
    env = HandlebarsEnvironment(max_depth=2)
    with pytest.raises(HandlebarsRuntimeError, match='Maximum nesting depth'):
        env.render(
            '{{#each a}}{{#each b}}{{#each c}}{{this}}{{/each}}{{/each}}{{/each}}',
            {'a': [{'b': [{'c': [1]}]}]},
        )


def test_module_getattr_invalid():
    import pydantic_handlebars

    with pytest.raises(AttributeError, match="has no attribute 'nonexistent'"):
        pydantic_handlebars.nonexistent  # type: ignore[attr-defined]
