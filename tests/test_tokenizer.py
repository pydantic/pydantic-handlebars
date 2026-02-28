"""Tests for the tokenizer.

Ported from handlebars.js spec/tokenizer.js.
"""

from pydantic_handlebars._tokenizer import TokenType, tokenize


def test_tokenizes_simple_mustache():
    tokens = tokenize('{{foo}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == [TokenType.OPEN, TokenType.ID, TokenType.CLOSE]


def test_tokenizes_triple_mustache():
    tokens = tokenize('{{{foo}}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == [TokenType.OPEN_UNESCAPED, TokenType.ID, TokenType.CLOSE_UNESCAPED]


def test_tokenizes_content():
    tokens = tokenize('Hello World')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == [TokenType.CONTENT]
    assert tokens[0].value == 'Hello World'


def test_tokenizes_content_and_mustache():
    tokens = tokenize('Hello {{name}}!')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == [TokenType.CONTENT, TokenType.OPEN, TokenType.ID, TokenType.CLOSE, TokenType.CONTENT]


def test_tokenizes_block_open():
    tokens = tokenize('{{#if}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == [TokenType.OPEN_BLOCK, TokenType.ID, TokenType.CLOSE]


def test_tokenizes_block_close():
    tokens = tokenize('{{/if}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == [TokenType.OPEN_ENDBLOCK, TokenType.ID, TokenType.CLOSE]


def test_tokenizes_inverse():
    tokens = tokenize('{{^}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == [TokenType.OPEN_INVERSE, TokenType.CLOSE]


def test_tokenizes_comment():
    tokens = tokenize('{{! comment }}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == [TokenType.COMMENT]


def test_tokenizes_long_comment():
    tokens = tokenize('{{!-- long comment --}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == [TokenType.COMMENT]


def test_tokenizes_path_separator():
    tokens = tokenize('{{foo.bar}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == [TokenType.OPEN, TokenType.ID, TokenType.SEP, TokenType.ID, TokenType.CLOSE]


def test_tokenizes_string_literal():
    tokens = tokenize('{{foo "bar"}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == [TokenType.OPEN, TokenType.ID, TokenType.STRING, TokenType.CLOSE]
    string_token = [t for t in tokens if t.type == TokenType.STRING][0]
    assert string_token.value == 'bar'


def test_tokenizes_number_literal():
    tokens = tokenize('{{foo 42}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == [TokenType.OPEN, TokenType.ID, TokenType.NUMBER, TokenType.CLOSE]
    number_token = [t for t in tokens if t.type == TokenType.NUMBER][0]
    assert number_token.value == '42'


def test_tokenizes_boolean():
    tokens = tokenize('{{foo true}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == [TokenType.OPEN, TokenType.ID, TokenType.BOOLEAN, TokenType.CLOSE]


def test_tokenizes_data_variable():
    tokens = tokenize('{{@index}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == [TokenType.OPEN, TokenType.DATA, TokenType.ID, TokenType.CLOSE]


def test_tokenizes_parent():
    tokens = tokenize('{{../foo}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == [TokenType.OPEN, TokenType.PARENT, TokenType.ID, TokenType.CLOSE]


def test_tokenizes_hash_args():
    tokens = tokenize('{{foo key=value}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == [TokenType.OPEN, TokenType.ID, TokenType.ID, TokenType.EQUALS, TokenType.ID, TokenType.CLOSE]


def test_tokenizes_subexpression():
    tokens = tokenize('{{foo (bar baz)}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == [
        TokenType.OPEN,
        TokenType.ID,
        TokenType.OPEN_SEXPR,
        TokenType.ID,
        TokenType.ID,
        TokenType.CLOSE_SEXPR,
        TokenType.CLOSE,
    ]


def test_tokenizes_else():
    tokens = tokenize('{{else}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == [TokenType.OPEN, TokenType.INVERSE, TokenType.CLOSE]


def test_tokenizes_strip_markers():
    tokens = tokenize('{{~foo~}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert TokenType.STRIP in types


def test_tokenizes_escaped_mustache():
    tokens = tokenize('\\{{foo}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == [TokenType.CONTENT]
    assert tokens[0].value == '{{foo}}'


def test_tokenizes_null():
    tokens = tokenize('{{null}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == [TokenType.OPEN, TokenType.NULL, TokenType.CLOSE]


def test_tokenizes_undefined():
    tokens = tokenize('{{undefined}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == [TokenType.OPEN, TokenType.UNDEFINED, TokenType.CLOSE]


def test_tokenizes_block_params():
    tokens = tokenize('{{#each items as |item|}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert TokenType.OPEN_BLOCK_PARAMS in types
    assert TokenType.CLOSE_BLOCK_PARAMS in types


def test_tokenizes_ampersand():
    tokens = tokenize('{{&foo}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    # {{& is tokenized as OPEN with value {{&
    assert types[0] == TokenType.OPEN


def test_tokenizes_single_quoted_string():
    tokens = tokenize("{{foo 'bar'}}")
    string_token = [t for t in tokens if t.type == TokenType.STRING][0]
    assert string_token.value == 'bar'


def test_tokenizes_negative_number():
    tokens = tokenize('{{foo -1}}')
    number_token = [t for t in tokens if t.type == TokenType.NUMBER][0]
    assert number_token.value == '-1'


def test_tokenizes_float():
    tokens = tokenize('{{foo 3.14}}')
    number_token = [t for t in tokens if t.type == TokenType.NUMBER][0]
    assert number_token.value == '3.14'


def test_tokenizes_bracket_notation():
    tokens = tokenize('{{[foo bar]}}')
    id_token = [t for t in tokens if t.type == TokenType.ID][0]
    assert id_token.value == 'foo bar'


def test_empty_template():
    tokens = tokenize('')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == []


def test_only_content():
    tokens = tokenize('Hello World')
    assert tokens[0].type == TokenType.CONTENT
    assert tokens[0].value == 'Hello World'
