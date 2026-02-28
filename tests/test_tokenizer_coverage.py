"""Additional tokenizer tests targeting uncovered code paths."""

import pytest

from pydantic_handlebars._exceptions import HandlebarsParseError
from pydantic_handlebars._tokenizer import TokenType, tokenize

# --- _peek returning empty string (line 115) ---


def test_peek_past_end_of_source():
    """When tokenizer peeks past end of source, it returns empty string."""
    # A simple template where the tokenizer will eventually peek past the end
    tokens = tokenize('{{a}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == [TokenType.OPEN, TokenType.ID, TokenType.CLOSE]


def test_peek_offset_past_end():
    """Peeking with offset past end of source returns empty string.

    When a dot is the last character in the template, _peek(1) returns ''
    which exercises the empty string return path in _peek.
    """
    # {{. - the dot is the last char, _peek(1) returns '' triggering line 115
    tokens = tokenize('{{.')
    ids = [t for t in tokens if t.type == TokenType.ID]
    assert len(ids) == 1
    assert ids[0].value == '.'


# --- Escaped mustache with another escaped mustache (lines 145-147) ---


def test_escaped_mustache_followed_by_escaped_mustache():
    r"""Escaped mustache \{{ followed by another \{{ in the read loop."""
    tokens = tokenize('\\{{foo}}\\{{bar}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    # Both escaped mustaches should be merged into one CONTENT token
    assert types == [TokenType.CONTENT]
    assert tokens[0].value == '{{foo}}{{bar}}'


def test_escaped_mustache_followed_by_real_mustache():
    r"""Escaped mustache \{{ followed by real {{ (line 149 break)."""
    tokens = tokenize('\\{{literal}}{{real}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == [TokenType.CONTENT, TokenType.OPEN, TokenType.ID, TokenType.CLOSE]
    assert tokens[0].value == '{{literal}}'


def test_escaped_mustache_followed_by_text_and_mustache():
    """Escaped mustache followed by some text then a real mustache."""
    tokens = tokenize('\\{{a}} stuff {{b}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == [TokenType.CONTENT, TokenType.OPEN, TokenType.ID, TokenType.CLOSE]
    assert tokens[0].value == '{{a}} stuff '


# --- Raw blocks (lines 156-157, 495-546) ---


def test_raw_block_basic():
    """Raw block with content."""
    tokens = tokenize('{{{{raw}}}}hello world{{{{/raw}}}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == [
        TokenType.OPEN_RAW_BLOCK,
        TokenType.ID,
        TokenType.CLOSE_RAW_BLOCK,
        TokenType.RAW_CONTENT,
        TokenType.END_RAW_BLOCK,
    ]
    # Check the raw content
    raw_tokens = [t for t in tokens if t.type == TokenType.RAW_CONTENT]
    assert raw_tokens[0].value == 'hello world'


def test_raw_block_preserves_mustaches():
    """Raw block preserves mustache syntax as raw content."""
    tokens = tokenize('{{{{raw}}}}{{not parsed}}{{{{/raw}}}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == [
        TokenType.OPEN_RAW_BLOCK,
        TokenType.ID,
        TokenType.CLOSE_RAW_BLOCK,
        TokenType.RAW_CONTENT,
        TokenType.END_RAW_BLOCK,
    ]
    raw_tokens = [t for t in tokens if t.type == TokenType.RAW_CONTENT]
    assert raw_tokens[0].value == '{{not parsed}}'


def test_raw_block_empty_content():
    """Raw block with no content between open and close."""
    tokens = tokenize('{{{{raw}}}}{{{{/raw}}}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == [
        TokenType.OPEN_RAW_BLOCK,
        TokenType.ID,
        TokenType.CLOSE_RAW_BLOCK,
        TokenType.END_RAW_BLOCK,
    ]


def test_raw_block_missing_name():
    """Raw block with no identifier should raise an error."""
    with pytest.raises(HandlebarsParseError, match='Expected identifier in raw block'):
        tokenize('{{{{ }}}}')


def test_raw_block_unclosed_open_tag():
    """Raw block with missing close for open tag."""
    with pytest.raises(HandlebarsParseError, match='Expected }}}}'):
        tokenize('{{{{raw}}')


def test_raw_block_unclosed():
    """Raw block that is never closed."""
    with pytest.raises(HandlebarsParseError, match='Unclosed raw block'):
        tokenize('{{{{raw}}}}some content but no close')


# --- _read_content producing no output (line 181->exit) ---


def test_content_empty_between_mustaches():
    """Two mustaches back to back should not emit empty content."""
    tokens = tokenize('{{a}}{{b}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == [
        TokenType.OPEN,
        TokenType.ID,
        TokenType.CLOSE,
        TokenType.OPEN,
        TokenType.ID,
        TokenType.CLOSE,
    ]
    # No CONTENT token should appear between them
    assert TokenType.CONTENT not in types


# --- Triple-stache with strip (lines 192-195) ---


def test_triple_stache_with_open_strip():
    """Triple-stache with strip on open."""
    tokens = tokenize('{{{~foo}}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert TokenType.OPEN_UNESCAPED in types
    assert TokenType.STRIP in types
    assert types[0] == TokenType.OPEN_UNESCAPED
    assert types[1] == TokenType.STRIP


# --- Long comment with strip close (lines 255-257) ---


def test_long_comment_with_strip_close():
    """Long comment closed with strip marker on close."""
    tokens = tokenize('{{!-- comment --~}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == [TokenType.COMMENT, TokenType.STRIP]
    assert tokens[0].value == ' comment '


# --- Unclosed long comment (line 263) ---


def test_unclosed_long_comment():
    """Unclosed long comment raises error."""
    with pytest.raises(HandlebarsParseError, match='Unclosed comment'):
        tokenize('{{!-- comment without close')


# --- Short comment with strip close (lines 267-269) ---


def test_short_comment_with_strip_close():
    """Short comment closed with strip marker."""
    tokens = tokenize('{{! comment ~}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == [TokenType.COMMENT, TokenType.STRIP]
    assert tokens[0].value == ' comment '


# --- Unclosed short comment (line 275) ---


def test_unclosed_short_comment():
    """Unclosed short comment raises error."""
    with pytest.raises(HandlebarsParseError, match='Unclosed comment'):
        tokenize('{{! comment without close')


# --- _read_mustache_body reaching end (lines 279->exit, 283) ---


def test_mustache_body_reaching_end_of_source():
    """Mustache opened but source ends without close produces tokens up to EOF."""
    tokens = tokenize('{{foo')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert TokenType.OPEN in types
    assert TokenType.ID in types


def test_mustache_body_only_whitespace_then_end():
    """Mustache body with only whitespace then EOF."""
    tokens = tokenize('{{foo   ')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert TokenType.OPEN in types
    assert TokenType.ID in types


# --- Strip before close in unescaped (lines 288-294) ---


def test_triple_stache_with_close_strip():
    """Triple-stache with strip on close."""
    tokens = tokenize('{{{foo~}}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert TokenType.OPEN_UNESCAPED in types
    assert TokenType.STRIP in types
    assert TokenType.CLOSE_UNESCAPED in types


# --- Strip in regular close (lines 295->305) ---


def test_regular_mustache_with_close_strip():
    """Regular mustache with strip on close."""
    tokens = tokenize('{{foo~}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert TokenType.OPEN in types
    assert TokenType.STRIP in types
    assert TokenType.CLOSE in types


# --- _read_expression_token at end of source (line 329) ---


def test_expression_token_at_end():
    """Exercise _read_expression_token returning immediately at end of source."""
    tokens = tokenize('{{x')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert TokenType.ID in types


# --- Mustache body no-progress break (lone '}' inside expression) ---


def test_mustache_body_no_progress_break():
    """A lone '}' that doesn't form '}}' or '}}}' causes the body loop to break."""
    tokens = tokenize('{{{unclosed}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert TokenType.OPEN_UNESCAPED in types
    assert TokenType.ID in types


# --- '.' as 'this' followed by '/' (lines 377-383) ---


def test_dot_this_followed_by_slash():
    """Dot used as 'this' followed by slash separator."""
    tokens = tokenize('{{./foo}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert TokenType.OPEN in types
    assert TokenType.ID in types
    assert TokenType.SEP in types
    # Should have . as ID, / as SEP, foo as ID
    ids = [t for t in tokens if t.type == TokenType.ID]
    assert ids[0].value == '.'
    assert ids[1].value == 'foo'


def test_dot_this_with_close():
    """Dot used as standalone 'this'."""
    tokens = tokenize('{{.}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == [TokenType.OPEN, TokenType.ID, TokenType.CLOSE]
    id_token = [t for t in tokens if t.type == TokenType.ID][0]
    assert id_token.value == '.'


# --- String escape sequences (lines 403-414) ---


def test_string_with_escape_newline():
    r"""String literal with \n escape."""
    tokens = tokenize('{{foo "hello\\nworld"}}')
    string_token = [t for t in tokens if t.type == TokenType.STRING][0]
    assert string_token.value == 'hello\nworld'


def test_string_with_escape_tab():
    r"""String literal with \t escape."""
    tokens = tokenize('{{foo "hello\\tworld"}}')
    string_token = [t for t in tokens if t.type == TokenType.STRING][0]
    assert string_token.value == 'hello\tworld'


def test_string_with_escape_return():
    r"""String literal with \r escape."""
    tokens = tokenize('{{foo "hello\\rworld"}}')
    string_token = [t for t in tokens if t.type == TokenType.STRING][0]
    assert string_token.value == 'hello\rworld'


def test_string_with_escape_quote():
    """String literal with escaped quote."""
    tokens = tokenize('{{foo "hello\\"world"}}')
    string_token = [t for t in tokens if t.type == TokenType.STRING][0]
    assert string_token.value == 'hello"world'


def test_string_with_escape_backslash():
    """String literal with escaped backslash."""
    tokens = tokenize('{{foo "hello\\\\world"}}')
    string_token = [t for t in tokens if t.type == TokenType.STRING][0]
    assert string_token.value == 'hello\\world'


# --- Unterminated string literal (line 421) ---


def test_unterminated_string():
    """Unterminated string literal raises error."""
    with pytest.raises(HandlebarsParseError, match='Unterminated string literal'):
        tokenize('{{foo "hello}}')


def test_unterminated_single_quoted_string():
    """Unterminated single-quoted string literal raises error."""
    with pytest.raises(HandlebarsParseError, match='Unterminated string literal'):
        tokenize("{{foo 'hello}}")


# --- Bracket notation without closing ] (line 451->453) ---


def test_bracket_notation_unclosed():
    """Bracket notation that reaches end of source without closing bracket."""
    tokens = tokenize('{{[foo')
    id_tokens = [t for t in tokens if t.type == TokenType.ID]
    assert len(id_tokens) == 1
    assert id_tokens[0].value == 'foo'


# --- Empty identifier / unexpected character (lines 460-464) ---


def test_unexpected_character_in_expression():
    """Unexpected character in expression raises error."""
    with pytest.raises(HandlebarsParseError, match='Unexpected character'):
        tokenize('{{%}}')


# --- 'as' not followed by '|' (lines 486-489) ---


def test_as_identifier_without_pipe():
    """The word 'as' used as a regular identifier (not followed by pipe)."""
    tokens = tokenize('{{as}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types == [TokenType.OPEN, TokenType.ID, TokenType.CLOSE]
    id_token = [t for t in tokens if t.type == TokenType.ID][0]
    assert id_token.value == 'as'


def test_as_identifier_followed_by_non_pipe():
    """The word 'as' followed by something other than pipe."""
    tokens = tokenize('{{as foo}}')
    # 'as' should be emitted as ID, then 'foo' as ID
    ids = [t for t in tokens if t.type == TokenType.ID]
    assert ids[0].value == 'as'
    assert ids[1].value == 'foo'


# --- Negative number (covers line 428-429 _read_number with minus) ---


def test_negative_number_in_expression():
    """Negative number like -42 in expression."""
    tokens = tokenize('{{foo -42}}')
    number_token = [t for t in tokens if t.type == TokenType.NUMBER][0]
    assert number_token.value == '-42'


# --- Partial open ---


def test_partial_open():
    """Partial open produces OPEN_PARTIAL token."""
    tokens = tokenize('{{> myPartial}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert types[0] == TokenType.OPEN_PARTIAL


# --- Strip on block open ---


def test_strip_on_block_open():
    """Strip marker on block open."""
    tokens = tokenize('{{~#each items}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert TokenType.OPEN_BLOCK in types
    assert TokenType.STRIP in types


# --- Strip on endblock ---


def test_strip_on_endblock():
    """Strip marker on endblock."""
    tokens = tokenize('{{~/each}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert TokenType.OPEN_ENDBLOCK in types
    assert TokenType.STRIP in types


# --- Strip on inverse ---


def test_strip_on_inverse():
    """Strip marker on inverse."""
    tokens = tokenize('{{~^}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert TokenType.OPEN_INVERSE in types
    assert TokenType.STRIP in types


# --- Content with escaped mustache inside content ---


def test_content_with_embedded_escaped_mustache():
    r"""Content that has \{{ inside it."""
    tokens = tokenize('before \\{{escaped}} after')
    content_tokens = [t for t in tokens if t.type == TokenType.CONTENT]
    combined = ''.join(t.value for t in content_tokens)
    assert '{{escaped}}' in combined
    assert 'before' in combined
    assert 'after' in combined


# --- Data variable @ not followed by alnum ---


def test_data_variable_at_sign_only():
    """@ not followed by alphanumeric still produces DATA token."""
    tokens = tokenize('{{@}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert TokenType.DATA in types


# --- Newline handling in _advance ---


def test_multiline_template():
    """Template with newlines tracks line numbers correctly."""
    tokens = tokenize('line1\n{{foo}}\nline3')
    foo_token = [t for t in tokens if t.type == TokenType.ID][0]
    assert foo_token.line == 2


# --- Dot as separator ---


def test_dot_separator_in_path():
    """Dot used as path separator in a path expression."""
    tokens = tokenize('{{foo.bar.baz}}')
    seps = [t for t in tokens if t.type == TokenType.SEP]
    assert len(seps) == 2
    assert all(s.value == '.' for s in seps)


# --- Slash as separator ---


def test_slash_separator_in_path():
    """Slash used as path separator."""
    tokens = tokenize('{{foo/bar}}')
    types = [t.type for t in tokens if t.type != TokenType.EOF]
    assert TokenType.SEP in types
    sep = [t for t in tokens if t.type == TokenType.SEP][0]
    assert sep.value == '/'
