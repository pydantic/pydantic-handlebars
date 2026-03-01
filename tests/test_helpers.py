"""Tests for helper calling conventions.

Ported from handlebars.js spec/helpers.js.
"""

# pyright: reportUnknownLambdaType=false, reportUnknownArgumentType=false, reportUnusedFunction=false, reportUnknownVariableType=false

from pydantic_handlebars import HandlebarsEnvironment, HelperOptions, SafeString, render

# --- Helper invocation ---


def test_helper_with_no_args():
    env = HandlebarsEnvironment()
    env.register_helper('hello', lambda *args, **kw: 'hello world')
    assert env.render('{{hello}}', {}) == 'hello world'


def test_helper_with_one_arg():
    env = HandlebarsEnvironment()
    env.register_helper('loud', lambda *args, **kw: str(args[0]).upper() if args else '')
    assert env.render('{{loud name}}', {'name': 'world'}) == 'WORLD'


def test_helper_with_multiple_args():
    env = HandlebarsEnvironment()
    env.register_helper(
        'combine', lambda *args, **kw: ' '.join(str(a) for a in args if not isinstance(a, HelperOptions))
    )
    assert env.render('{{combine a b c}}', {'a': 'x', 'b': 'y', 'c': 'z'}) == 'x y z'


def test_helper_with_hash_args():
    env = HandlebarsEnvironment()

    def link(*args: object, options: HelperOptions) -> SafeString:
        url = options.hash.get('url', '#')
        text = options.hash.get('text', '')
        return SafeString(f'<a href="{url}">{text}</a>')

    env.register_helper('link', link)
    assert env.render('{{link url="http://example.com" text="click"}}', {}) == '<a href="http://example.com">click</a>'


def test_helper_with_mixed_args_and_hash():
    env = HandlebarsEnvironment()

    def format_name(*args: object, options: HelperOptions) -> str:
        name = str(args[0]) if args else ''
        title = options.hash.get('title', '')
        return f'{title} {name}' if title else name

    env.register_helper('format_name', format_name)
    assert env.render('{{format_name name title="Dr."}}', {'name': 'Alice'}) == 'Dr. Alice'


# --- Helper escaping ---


def test_helper_output_not_escaped_by_default():
    env = HandlebarsEnvironment()
    env.register_helper('html', lambda *args, **kw: '<b>bold</b>')
    assert env.render('{{html}}', {}) == '<b>bold</b>'


def test_helper_output_is_escaped_when_enabled():
    env = HandlebarsEnvironment(auto_escape=True)
    env.register_helper('html', lambda *args, **kw: '<b>bold</b>')
    assert env.render('{{html}}', {}) == '&lt;b&gt;bold&lt;/b&gt;'


def test_helper_output_unescaped_with_triple_stache():
    env = HandlebarsEnvironment()
    env.register_helper('html', lambda *args, **kw: '<b>bold</b>')
    assert env.render('{{{html}}}', {}) == '<b>bold</b>'


# --- Block helpers ---


def test_block_helper_basic():
    env = HandlebarsEnvironment()

    def noop(context: object, *args: object, options: HelperOptions) -> str:
        return options.fn(context)

    env.register_helper('noop', noop)
    assert env.render('{{#noop}}content{{/noop}}', {}) == 'content'


def test_block_helper_with_else():
    env = HandlebarsEnvironment()

    def conditional(context: object, *args: object, options: HelperOptions) -> str:
        if args and args[0]:
            return options.fn(context)
        return options.inverse(context)

    env.register_helper('conditional', conditional)
    assert env.render('{{#conditional show}}yes{{else}}no{{/conditional}}', {'show': True}) == 'yes'
    assert env.render('{{#conditional show}}yes{{else}}no{{/conditional}}', {'show': False}) == 'no'


def test_block_helper_with_hash():
    env = HandlebarsEnvironment()

    def repeat(context: object, *args: object, options: HelperOptions) -> str:
        times = int(options.hash.get('times', 1))
        return ''.join(options.fn(context) for _ in range(times))

    env.register_helper('repeat', repeat)
    assert env.render('{{#repeat times=3}}Ho {{/repeat}}', {}) == 'Ho Ho Ho '


def test_block_helper_context_change():
    env = HandlebarsEnvironment()

    def wrap(context: object, *args: object, options: HelperOptions) -> str:
        new_ctx = args[0] if args else context
        return options.fn(new_ctx)

    env.register_helper('wrap', wrap)
    assert env.render('{{#wrap person}}{{name}}{{/wrap}}', {'person': {'name': 'Alice'}}) == 'Alice'


# --- Helper decorator ---


def test_helper_decorator():
    env = HandlebarsEnvironment()

    @env.helper
    def shout(*args: object, **kw: object) -> str:
        val = str(args[0]) if args else ''
        return val.upper() + '!!!'

    assert env.render('{{shout name}}', {'name': 'world'}) == 'WORLD!!!'


def test_helper_decorator_with_name():
    env = HandlebarsEnvironment()

    @env.helper('yell')
    def my_yell(*args: object, **kw: object) -> str:
        val = str(args[0]) if args else ''
        return val.upper() + '!!!'

    assert env.render('{{yell name}}', {'name': 'hello'}) == 'HELLO!!!'


# --- Helper priority ---


def test_helper_takes_priority_over_context():
    env = HandlebarsEnvironment()
    env.register_helper('foo', lambda *args, **kw: 'helper')
    assert env.render('{{foo}}', {'foo': 'context'}) == 'helper'


def test_context_used_when_no_helper():
    assert render('{{foo}}', {'foo': 'context'}) == 'context'
