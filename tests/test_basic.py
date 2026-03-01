"""Basic tests for Handlebars template rendering.

Ported from handlebars.js spec/basic.js.
"""

# pyright: reportUnknownLambdaType=false, reportUnknownArgumentType=false

from pydantic_handlebars import HandlebarsEnvironment, render

# --- Most basic ---


def test_most_basic():
    assert render('{{foo}}', {'foo': 'foo'}) == 'foo'


def test_compiling_with_a_basic_context():
    assert render('Goodbye\n{{cruel}}\n{{world}}!', {'cruel': 'cruel', 'world': 'world'}) == 'Goodbye\ncruel\nworld!'


def test_compiling_with_an_undefined_context():
    assert render('Goodbye\n{{cruel}}\n{{world}}!', {}) == 'Goodbye\n\n!'


def test_comments():
    assert (
        render('{{! Goodbye}}Goodbye\n{{cruel}}\n{{world}}!', {'cruel': 'cruel', 'world': 'world'})
        == 'Goodbye\ncruel\nworld!'
    )


def test_long_comments():
    assert (
        render('{{!-- long comment --}}Goodbye\n{{cruel}}\n{{world}}!', {'cruel': 'cruel', 'world': 'world'})
        == 'Goodbye\ncruel\nworld!'
    )


def test_long_comment_with_close_brace():
    assert (
        render('{{!-- long }} comment --}}Goodbye\n{{cruel}}\n{{world}}!', {'cruel': 'cruel', 'world': 'world'})
        == 'Goodbye\ncruel\nworld!'
    )


def test_boolean_false():
    assert render('{{val1}} {{val2}}', {'val1': False, 'val2': False}) == 'false false'


def test_zeros():
    assert render('{{num1}} {{num2}}', {'num1': 0, 'num2': 0}) == '0 0'


def test_false_and_zero_are_not_empty():
    """Ensure false and 0 render as strings, not empty."""
    assert render('{{val}}', {'val': False}) == 'false'
    assert render('{{val}}', {'val': 0}) == '0'


# --- Escaping ---


def test_escaping_expressions():
    env = HandlebarsEnvironment(auto_escape=True)
    assert env.render('{{awesome}}', {'awesome': "&'\\<>"}) == '&amp;&#x27;\\&lt;&gt;'


def test_triple_stache():
    assert render('{{{awesome}}}', {'awesome': "&'\\<>"}) == "&'\\<>"


def test_triple_stache_with_html():
    assert render('{{{foo}}}', {'foo': '<b>bold</b>'}) == '<b>bold</b>'


def test_ampersand_unescaped():
    assert render('{{&awesome}}', {'awesome': "&'\\<>"}) == "&'\\<>"


# --- Paths ---


def test_simple_path():
    assert render('{{person.name}}', {'person': {'name': 'Alan'}}) == 'Alan'


def test_deeply_nested_path():
    assert render('{{a.b.c.d}}', {'a': {'b': {'c': {'d': 'deep'}}}}) == 'deep'


def test_missing_path_returns_empty():
    assert render('{{a.b.c}}', {'a': {}}) == ''


def test_this_keyword():
    assert render('{{#each items}}{{this}} {{/each}}', {'items': ['a', 'b', 'c']}) == 'a b c '


def test_this_dot_name():
    assert (
        render('{{#each people}}{{this.name}} {{/each}}', {'people': [{'name': 'Alice'}, {'name': 'Bob'}]})
        == 'Alice Bob '
    )


# --- Literals ---


def test_string_literal():
    env = HandlebarsEnvironment()
    env.register_helper('echo', lambda *args, **kw: str(args[0]) if args else '')
    assert env.render('{{echo "hello"}}', {}) == 'hello'


def test_number_literal():
    env = HandlebarsEnvironment()
    env.register_helper('echo', lambda *args, **kw: str(args[0]) if args else '')
    assert env.render('{{echo 42}}', {}) == '42'


def test_boolean_literal():
    env = HandlebarsEnvironment()
    env.register_helper('echo', lambda *args, **kw: str(args[0]) if args else '')
    assert env.render('{{echo true}}', {}) == 'True'


def test_null_literal():
    env = HandlebarsEnvironment()
    env.register_helper('echo', lambda *args, **kw: str(args[0]) if args else '')
    assert env.render('{{echo null}}', {}) == 'None'


# --- Content ---


def test_simple_content():
    assert render('Hello World!', {}) == 'Hello World!'


def test_content_with_newlines():
    assert render('Hello\nWorld\n!', {}) == 'Hello\nWorld\n!'


# --- Escaped mustaches ---


def test_escaped_mustache():
    assert render('\\{{foo}}', {'foo': 'bar'}) == '{{foo}}'


def test_escaped_mustache_with_content():
    assert render('content \\{{foo}}', {'foo': 'bar'}) == 'content {{foo}}'


# --- Rendering values ---


def test_undefined_renders_empty():
    assert render('{{missing}}', {}) == ''


def test_null_renders_empty():
    assert render('{{val}}', {'val': None}) == ''


def test_list_renders_as_string():
    result = render('{{val}}', {'val': [1, 2, 3]})
    assert result == '[1, 2, 3]'


def test_nested_undefined_renders_empty():
    assert render('{{foo.bar.baz}}', {'foo': {'bar': {}}}) == ''


# --- Mixed content ---


def test_mixed_content_and_expressions():
    assert (
        render('Hello {{name}}, you are {{age}} years old!', {'name': 'Alice', 'age': 30})
        == 'Hello Alice, you are 30 years old!'
    )


def test_multiple_expressions():
    assert render('{{a}} {{b}} {{c}}', {'a': '1', 'b': '2', 'c': '3'}) == '1 2 3'


# --- Whitespace handling ---


def test_preserves_whitespace():
    assert render('  {{foo}}  ', {'foo': 'bar'}) == '  bar  '


def test_preserves_newlines():
    assert render('\n{{foo}}\n', {'foo': 'bar'}) == '\nbar\n'


# --- Edge cases ---


def test_empty_template():
    assert render('', {}) == ''


def test_template_with_only_content():
    assert render('Hello World', {}) == 'Hello World'


def test_template_with_only_expression():
    assert render('{{foo}}', {'foo': 'bar'}) == 'bar'


def test_hyphenated_key():
    assert render('{{foo-bar}}', {'foo-bar': 'baz'}) == 'baz'


def test_nested_hyphenated_key():
    assert render('{{foo.bar-baz}}', {'foo': {'bar-baz': 'qux'}}) == 'qux'


def test_bracket_notation():
    assert render('{{[foo bar]}}', {'foo bar': 'baz'}) == 'baz'


# --- Numeric array index in dot-notation ---


def test_numeric_index_first():
    assert render('{{items.0}}', {'items': ['a', 'b', 'c']}) == 'a'


def test_numeric_index_second():
    assert render('{{items.1}}', {'items': ['a', 'b', 'c']}) == 'b'


def test_numeric_index_nested():
    assert render('{{data.items.0.name}}', {'data': {'items': [{'name': 'Alice'}, {'name': 'Bob'}]}}) == 'Alice'


def test_numeric_index_this_dot():
    assert render('{{#each items}}{{this.0}}{{/each}}', {'items': [['x', 'y']]}) == 'x'


def test_numeric_index_dot_slash():
    assert render('{{#each items}}{{./0}}{{/each}}', {'items': [['x', 'y']]}) == 'x'


def test_numeric_index_out_of_bounds():
    assert render('{{items.5}}', {'items': ['a', 'b', 'c']}) == ''
