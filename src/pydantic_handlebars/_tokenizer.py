"""Tokenizer for Handlebars templates.

Converts a template string into a stream of tokens that the parser can consume.

The tokenizer supports configurable open/close delimiters (defaulting to `{{`
and `}}`). When non-default delimiters are used, triple-stache (`{{{...}}}`)
and raw-block (`{{{{...}}}}`) features are disabled — those forms only have
unambiguous extensions for the default delimiter pair and are rarely needed in
the embedding scenarios that motivate configurable delimiters.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto

from pydantic_handlebars._exceptions import HandlebarsParseError

DEFAULT_OPEN_DELIM = '{{'
DEFAULT_CLOSE_DELIM = '}}'


class TokenType(Enum):
    """Types of tokens produced by the tokenizer."""

    # Content
    CONTENT = auto()

    # Comments
    COMMENT = auto()

    # Mustache delimiters
    OPEN = auto()  # {{
    CLOSE = auto()  # }}
    OPEN_UNESCAPED = auto()  # {{{
    CLOSE_UNESCAPED = auto()  # }}}
    OPEN_BLOCK = auto()  # {{#
    OPEN_ENDBLOCK = auto()  # {{/
    OPEN_INVERSE = auto()  # {{^
    OPEN_PARTIAL = auto()  # {{>

    # Raw block delimiters
    OPEN_RAW_BLOCK = auto()  # {{{{
    CLOSE_RAW_BLOCK = auto()  # }}}}
    END_RAW_BLOCK = auto()  # {{{{/
    RAW_CONTENT = auto()  # Content inside raw block

    # Expression components
    ID = auto()  # identifier
    DATA = auto()  # @data variable prefix
    SEP = auto()  # . or / separator
    PARENT = auto()  # ../
    OPEN_SEXPR = auto()  # (
    CLOSE_SEXPR = auto()  # )
    EQUALS = auto()  # = (in hash args)
    STRING = auto()  # "string" or 'string'
    NUMBER = auto()  # 42, 3.14, -1
    BOOLEAN = auto()  # true, false
    UNDEFINED = auto()  # undefined
    NULL = auto()  # null
    INVERSE = auto()  # else or ^

    # Block params
    OPEN_BLOCK_PARAMS = auto()  # as |
    CLOSE_BLOCK_PARAMS = auto()  # |

    # Whitespace control
    STRIP = auto()  # ~

    # End of input
    EOF = auto()


@dataclass(slots=True)
class Token:
    """A single token from the tokenizer.

    Attributes:
        type: The type of token.
        value: The string value of the token.
        line: Line number (1-based).
        column: Column number (1-based).
    """

    type: TokenType
    value: str
    line: int
    column: int


@dataclass(frozen=True, slots=True)
class _Delimiters:
    r"""Pre-computed delimiter strings for the tokenizer.

    All delimiter-derived literals (`{{#`, `{{/`, `\{{`, `~}}`, …)
    are computed once at construction so the tokenizer's hot path doesn't
    re-concatenate them per token.
    """

    open: str
    """The open delimiter, e.g. `{{` or `@{`."""
    close: str
    """The close delimiter, e.g. `}}` or `}@`."""
    open_block: str
    open_endblock: str
    open_inverse: str
    open_partial: str
    open_unescape_amp: str
    """Open + `&` — the legacy unescaped variant (`{{&foo}}`)."""
    open_comment: str
    strip_open: str
    """Open + `~` — open-strip whitespace control."""
    strip_close: str
    """`~` + close — close-strip whitespace control."""
    close_long_comment: str
    """`--` + close — closing tag of a long `{{!-- … --}}` comment."""
    close_long_comment_strip: str
    """`--~` + close — long-comment close with close-strip."""
    triple_open: str | None
    """Open + `{` (only enabled for the default `{{` open delimiter)."""
    triple_close: str | None
    triple_strip_close: str | None
    raw_open: str | None
    """Open + open (only enabled for the default delimiters)."""
    raw_close: str | None
    end_raw_block_prefix: str | None
    """Raw-open + `/` — the start of a raw block end tag."""
    close_first_char: str
    """First char of the close delimiter — used to detect end-of-expression
    inside a mustache body without committing to consuming the full close."""


def _validate_delimiters(open_delim: str, close_delim: str) -> None:
    """Reject delimiter choices that would confuse the tokenizer or parser.

    The constraints are conservative — they cover the cases where the tokenizer
    could not unambiguously distinguish a delimiter boundary from the inner
    expression syntax. In particular:

    * Empty or identical open/close cannot be tokenised.
    * A whitespace-prefixed open / suffixed close is ambiguous because the
      tokenizer skips whitespace inside expressions when looking for the close.
    * Characters that are syntactically meaningful inside an expression body
      (string quotes, parentheses, `=`, `|`) cannot appear in either
      delimiter without making expressions un-parsable.
    * `~` cannot appear in either delimiter because it is the whitespace-
      control marker (`{{~` / `~}}` etc.).
    """
    if not open_delim or not close_delim:
        raise ValueError('open_delim and close_delim must be non-empty')
    if open_delim == close_delim:
        raise ValueError('open_delim and close_delim must differ')
    if open_delim[0].isspace() or close_delim[-1].isspace():
        raise ValueError('open_delim must not start with whitespace and close_delim must not end with whitespace')
    forbidden = set('"\'()=|~')
    bad_open = forbidden & set(open_delim)
    if bad_open:
        raise ValueError(f'open_delim must not contain any of {"".join(sorted(forbidden))!r}; got {open_delim!r}')
    bad_close = forbidden & set(close_delim)
    if bad_close:
        raise ValueError(f'close_delim must not contain any of {"".join(sorted(forbidden))!r}; got {close_delim!r}')


def _make_delimiters(open_delim: str, close_delim: str) -> _Delimiters:
    """Build a `_Delimiters` config from raw open/close strings."""
    _validate_delimiters(open_delim, close_delim)
    is_default = open_delim == DEFAULT_OPEN_DELIM and close_delim == DEFAULT_CLOSE_DELIM
    triple_open = DEFAULT_OPEN_DELIM + '{' if is_default else None  # i.e. '{{{'
    triple_close = '}' + DEFAULT_CLOSE_DELIM if is_default else None  # i.e. '}}}'
    triple_strip_close = '~' + triple_close if triple_close is not None else None
    raw_open = DEFAULT_OPEN_DELIM + DEFAULT_OPEN_DELIM if is_default else None  # i.e. '{{{{'
    raw_close = DEFAULT_CLOSE_DELIM + DEFAULT_CLOSE_DELIM if is_default else None
    end_raw_block_prefix = raw_open + '/' if raw_open is not None else None
    return _Delimiters(
        open=open_delim,
        close=close_delim,
        open_block=open_delim + '#',
        open_endblock=open_delim + '/',
        open_inverse=open_delim + '^',
        open_partial=open_delim + '>',
        open_unescape_amp=open_delim + '&',
        open_comment=open_delim + '!',
        strip_open=open_delim + '~',
        strip_close='~' + close_delim,
        close_long_comment='--' + close_delim,
        close_long_comment_strip='--~' + close_delim,
        triple_open=triple_open,
        triple_close=triple_close,
        triple_strip_close=triple_strip_close,
        raw_open=raw_open,
        raw_close=raw_close,
        end_raw_block_prefix=end_raw_block_prefix,
        close_first_char=close_delim[0],
    )


def tokenize(
    source: str,
    *,
    open_delim: str = DEFAULT_OPEN_DELIM,
    close_delim: str = DEFAULT_CLOSE_DELIM,
) -> list[Token]:
    """Tokenize a Handlebars template string.

    Args:
        source: The template string to tokenize.
        open_delim: The opening mustache delimiter. Defaults to `{{`.
        close_delim: The closing mustache delimiter. Defaults to `}}`.

    Returns:
        A list of tokens.

    Raises:
        ValueError: If the delimiter pair is invalid (empty, identical,
            whitespace-prefixed/suffixed, or contains characters reserved
            for expression syntax).
        HandlebarsParseError: If the template has a tokenizer-level error.
    """
    return _TemplateTokenizer(source, _make_delimiters(open_delim, close_delim)).tokenize()


class _TemplateTokenizer:
    """Tokenizes a Handlebars template string into a sequence of tokens."""

    def __init__(self, source: str, delims: _Delimiters) -> None:
        self._source = source
        self._delims = delims
        self._pos = 0
        self._line = 1
        self._column = 1
        self._tokens: list[Token] = []

    def tokenize(self) -> list[Token]:
        """Tokenize the entire template."""
        while self._pos < len(self._source):
            self._read_next()
        self._tokens.append(Token(TokenType.EOF, '', self._line, self._column))
        return self._tokens

    def _peek(self, offset: int = 0) -> str:
        pos = self._pos + offset
        if pos < len(self._source):
            return self._source[pos]
        return ''

    def _starts_with(self, text: str) -> bool:
        return self._source[self._pos : self._pos + len(text)] == text

    def _advance(self, count: int = 1) -> str:
        text = self._source[self._pos : self._pos + count]
        for ch in text:
            if ch == '\n':
                self._line += 1
                self._column = 1
            else:
                self._column += 1
        self._pos += count
        return text

    def _emit(self, token_type: TokenType, value: str, line: int, column: int) -> None:
        self._tokens.append(Token(token_type, value, line, column))

    def _read_next(self) -> None:
        """Read the next token(s) from the source."""
        d = self._delims
        # Check for raw block (only with default delims): {{{{
        if (
            d.raw_open is not None
            and d.end_raw_block_prefix is not None
            and self._starts_with(d.raw_open)
            and not self._starts_with(d.end_raw_block_prefix)
        ):
            self._read_raw_block()
            return

        # Check for mustache open. Escape handling (`\<open>` → literal open)
        # lives inside `_read_content` so it can count consecutive
        # backslashes — see `_consume_backslash_run` for the parity rule.
        if self._starts_with(d.open):
            self._read_mustache()
            return

        self._read_content()

    def _read_content(self) -> None:
        """Read plain text content."""
        d = self._delims
        line, col = self._line, self._column
        content: list[str] = []

        while self._pos < len(self._source):
            if self._source[self._pos] == '\\':
                if not self._consume_backslash_run(content):
                    # Even-length backslash run preceding the open delimiter:
                    # contributes literal backslashes (already appended) and
                    # then yields control so the mustache parser takes over.
                    break
                continue
            if self._starts_with(d.open):
                break
            content.append(self._advance())

        if content:  # pragma: no branch
            self._emit(TokenType.CONTENT, ''.join(content), line, col)

    def _consume_backslash_run(self, content: list[str]) -> bool:
        r"""Consume a run of backslashes and, if followed by an open delimiter, apply the escape rule.

        Handlebars.js semantics, which `pydantic-handlebars` follows: a run of
        N backslashes immediately before an open delimiter contributes
        `N // 2` literal backslashes to the output; the open delimiter is
        then treated as literal content if N is odd (`\{{x}}` → literal
        `{{x}}`) or as the start of a real mustache expression if N is
        even (`\\{{x}}` → `\` + rendered X).

        Returns `True` when the caller should keep reading content, and
        `False` when the run ended on an even-length boundary that yields
        to the mustache parser.
        """
        d = self._delims
        run_start = self._pos
        while self._pos < len(self._source) and self._source[self._pos] == '\\':
            self._advance(1)
        run_len = self._pos - run_start

        if not self._starts_with(d.open):
            # Backslashes that aren't followed by an open delimiter are plain
            # content — emit them verbatim and let the loop continue.
            content.append('\\' * run_len)
            return True

        literal_count = run_len // 2
        if literal_count:
            content.append('\\' * literal_count)
        if run_len % 2 == 1:
            # Odd → the last backslash escapes the open delimiter; consume
            # the open delimiter as literal content and keep reading.
            content.append(self._advance(len(d.open)))
            return True
        # Even → all backslashes were literal pairs; yield to the mustache
        # parser to consume the open delimiter as a real expression start.
        return False

    def _read_mustache(self) -> None:
        """Read a mustache tag (open ... close)."""
        d = self._delims
        line, col = self._line, self._column

        # Triple-stache (unescaped): only available with default delims.
        if (
            d.triple_open is not None
            and self._starts_with(d.triple_open)
            # `{{{{` is raw-block-open, not triple-stache; the raw-block
            # branch handles it first, but we still need to avoid mis-reading
            # it here if the caller invoked _read_mustache directly.
            and not (d.raw_open is not None and self._starts_with(d.raw_open))
        ):
            self._advance(len(d.triple_open))
            if self._peek() == '~':
                strip_l, strip_c = self._line, self._column
                self._advance()
                self._emit(TokenType.OPEN_UNESCAPED, d.triple_open, line, col)
                self._emit(TokenType.STRIP, '~', strip_l, strip_c)
            else:
                self._emit(TokenType.OPEN_UNESCAPED, d.triple_open, line, col)
            self._read_mustache_body(close_unescaped=True)
            return

        # Regular open
        self._advance(len(d.open))
        self._read_regular_mustache(line, col)

    def _read_regular_mustache(self, line: int, col: int) -> None:
        """Read a regular mustache tag after consuming the open delim."""
        d = self._delims
        open_strip = False
        if self._peek() == '~':
            open_strip = True
            self._advance()

        next_ch = self._peek()

        if next_ch == '!':
            self._read_comment(line, col, open_strip)
            return

        # Map special characters to their token types. The emitted `value`
        # is the *original* delim-with-suffix string (so error messages and
        # round-trips reflect the actual source delimiter pair).
        special_map: dict[str, tuple[TokenType, str]] = {
            '#': (TokenType.OPEN_BLOCK, d.open_block),
            '/': (TokenType.OPEN_ENDBLOCK, d.open_endblock),
            '^': (TokenType.OPEN_INVERSE, d.open_inverse),
            '&': (TokenType.OPEN, d.open_unescape_amp),
            '>': (TokenType.OPEN_PARTIAL, d.open_partial),
        }

        if next_ch in special_map:
            self._advance()
            token_type, value = special_map[next_ch]
            if open_strip and next_ch == '^':
                # For ^, emit STRIP before OPEN_INVERSE so the parser can
                # distinguish open-strip from close-strip on the inverse
                # tag — other special chars always have content separating
                # the two strip positions.
                self._emit(TokenType.STRIP, '~', line, col + len(d.open))
                self._emit(token_type, value, line, col)
            else:
                self._emit(token_type, value, line, col)
                if open_strip:
                    self._emit(TokenType.STRIP, '~', line, col + len(d.open))
            self._read_mustache_body()
            return

        # Regular open
        self._emit(TokenType.OPEN, d.open, line, col)
        if open_strip:
            self._emit(TokenType.STRIP, '~', line, col + len(d.open))
        self._read_mustache_body()

    def _read_comment(self, open_line: int, open_col: int, open_strip: bool) -> None:
        """Read a comment tag, emitting strip markers for whitespace control."""
        d = self._delims
        self._advance()  # consume !

        long_comment = self._starts_with('--')
        if long_comment:
            self._advance(2)

        comment_parts: list[str] = []

        if long_comment:
            while self._pos < len(self._source):
                if self._starts_with(d.close_long_comment_strip):
                    self._advance(2)  # consume --
                    if open_strip:
                        self._emit(TokenType.STRIP, '~', open_line, open_col + len(d.open))
                    self._emit(TokenType.COMMENT, ''.join(comment_parts), open_line, open_col)
                    strip_l, strip_c = self._line, self._column
                    self._advance(1)  # consume ~
                    self._emit(TokenType.STRIP, '~', strip_l, strip_c)
                    self._advance(len(d.close))  # consume close
                    return
                if self._starts_with(d.close_long_comment):
                    self._advance(2)  # consume --
                    if open_strip:
                        self._emit(TokenType.STRIP, '~', open_line, open_col + len(d.open))
                    self._emit(TokenType.COMMENT, ''.join(comment_parts), open_line, open_col)
                    self._advance(len(d.close))  # consume close
                    return
                comment_parts.append(self._advance())
            raise HandlebarsParseError('Unclosed comment', line=open_line, column=open_col)
        else:
            while self._pos < len(self._source):
                if self._starts_with(d.strip_close):
                    if open_strip:
                        self._emit(TokenType.STRIP, '~', open_line, open_col + len(d.open))
                    self._emit(TokenType.COMMENT, ''.join(comment_parts), open_line, open_col)
                    strip_l, strip_c = self._line, self._column
                    self._advance(1)  # consume ~
                    self._emit(TokenType.STRIP, '~', strip_l, strip_c)
                    self._advance(len(d.close))  # consume close
                    return
                if self._starts_with(d.close):
                    if open_strip:
                        self._emit(TokenType.STRIP, '~', open_line, open_col + len(d.open))
                    self._emit(TokenType.COMMENT, ''.join(comment_parts), open_line, open_col)
                    self._advance(len(d.close))  # consume close
                    return
                comment_parts.append(self._advance())
            raise HandlebarsParseError('Unclosed comment', line=open_line, column=open_col)

    def _read_mustache_body(self, close_unescaped: bool = False) -> None:
        """Read the body of a mustache tag."""
        d = self._delims
        while self._pos < len(self._source):
            self._skip_ws()

            if self._pos >= len(self._source):
                break

            # Check for strip before close: ~<triple-close> or ~<close>
            if self._peek() == '~':
                if (
                    close_unescaped
                    and d.triple_strip_close is not None
                    and d.triple_close is not None
                    and self._starts_with(d.triple_strip_close)
                ):
                    strip_l, strip_c = self._line, self._column
                    self._advance()  # ~
                    self._emit(TokenType.STRIP, '~', strip_l, strip_c)
                    close_l, close_c = self._line, self._column
                    self._advance(len(d.triple_close))
                    self._emit(TokenType.CLOSE_UNESCAPED, d.triple_close, close_l, close_c)
                    return
                if self._starts_with(d.strip_close):  # pragma: no branch
                    strip_l, strip_c = self._line, self._column
                    self._advance()  # ~
                    self._emit(TokenType.STRIP, '~', strip_l, strip_c)
                    close_l, close_c = self._line, self._column
                    self._advance(len(d.close))
                    self._emit(TokenType.CLOSE, d.close, close_l, close_c)
                    return

            # Close unescaped: triple-close
            if close_unescaped and d.triple_close is not None and self._starts_with(d.triple_close):
                close_l, close_c = self._line, self._column
                self._advance(len(d.triple_close))
                self._emit(TokenType.CLOSE_UNESCAPED, d.triple_close, close_l, close_c)
                return

            # Close
            if self._starts_with(d.close):
                close_l, close_c = self._line, self._column
                self._advance(len(d.close))
                self._emit(TokenType.CLOSE, d.close, close_l, close_c)
                return

            # Read an expression token; track position to detect no-progress loops
            saved_pos = self._pos
            self._read_expression_token()
            if self._pos == saved_pos:
                # No progress — stuck on a character that doesn't form a
                # close delim or a valid expression token. Break out so the
                # parser can report a structured error.
                break

    def _skip_ws(self) -> None:
        """Skip whitespace inside a mustache expression."""
        while self._pos < len(self._source) and self._peek() in (' ', '\t', '\n', '\r'):
            self._advance()

    def _read_expression_token(self) -> None:
        """Read a single expression token."""
        if self._pos >= len(self._source):
            return  # pragma: no cover

        ch = self._peek()
        line, col = self._line, self._column

        if ch == '(':
            self._advance()
            self._emit(TokenType.OPEN_SEXPR, '(', line, col)
            return

        if ch == ')':
            self._advance()
            self._emit(TokenType.CLOSE_SEXPR, ')', line, col)
            return

        if ch == '=':
            self._advance()
            self._emit(TokenType.EQUALS, '=', line, col)
            return

        if ch == '|':
            self._advance()
            self._emit(TokenType.CLOSE_BLOCK_PARAMS, '|', line, col)
            return

        if ch in ('"', "'"):
            self._read_string()
            return

        if ch.isdigit() or (ch == '-' and self._peek(1).isdigit()):
            self._read_number()
            return

        if ch == '@':
            self._advance()
            self._emit(TokenType.DATA, '@', line, col)
            if self._pos < len(self._source) and (self._peek().isalnum() or self._peek() == '_'):
                self._read_id()
            return

        # Check for ../ before checking .
        if self._starts_with('../'):
            self._advance(3)
            self._emit(TokenType.PARENT, '../', line, col)
            return

        # Check for . as 'this' (standalone or followed by / or space or close).
        # The close-delim's first char terminates the expression body the same
        # way `}` does for the default `}}` delim, so it counts as a
        # "close-like" sentinel here.
        close_first = self._delims.close_first_char
        if ch == '.' and self._peek(1) in ('', ' ', close_first, '~', ')', '/', '\t', '\n', '\r'):
            self._advance()
            self._emit(TokenType.ID, '.', line, col)
            if self._pos < len(self._source) and self._peek() == '/':
                sep_l, sep_c = self._line, self._column
                self._advance()
                self._emit(TokenType.SEP, '/', sep_l, sep_c)
            return

        # Path separators
        if ch in ('.', '/'):
            self._advance()
            self._emit(TokenType.SEP, ch, line, col)
            return

        # Identifier
        self._read_id()

    def _read_string(self) -> None:
        """Read a string literal."""
        line, col = self._line, self._column
        quote = self._advance()
        value: list[str] = []

        while self._pos < len(self._source):
            ch = self._peek()
            if ch == '\\':
                self._advance()
                if self._pos < len(self._source):  # pragma: no branch
                    escaped = self._advance()
                    if escaped == 'n':
                        value.append('\n')
                    elif escaped == 't':
                        value.append('\t')
                    elif escaped == 'r':
                        value.append('\r')
                    else:
                        value.append(escaped)
                continue
            if ch == quote:
                self._advance()
                self._emit(TokenType.STRING, ''.join(value), line, col)
                return
            value.append(self._advance())

        raise HandlebarsParseError('Unterminated string literal', line=line, column=col)

    def _read_number(self) -> None:
        """Read a number literal."""
        line, col = self._line, self._column
        num: list[str] = []

        if self._peek() == '-':
            num.append(self._advance())

        while self._pos < len(self._source) and self._peek().isdigit():
            num.append(self._advance())

        if self._pos < len(self._source) and self._peek() == '.' and self._peek(1).isdigit():
            num.append(self._advance())
            while self._pos < len(self._source) and self._peek().isdigit():
                num.append(self._advance())

        self._emit(TokenType.NUMBER, ''.join(num), line, col)

    def _read_id(self) -> None:
        """Read an identifier."""
        line, col = self._line, self._column
        value: list[str] = []

        # Bracket notation
        if self._pos < len(self._source) and self._peek() == '[':
            self._advance()
            while self._pos < len(self._source) and self._peek() != ']':
                value.append(self._advance())
            if self._pos < len(self._source):
                self._advance()  # skip ]
            self._emit(TokenType.ID, ''.join(value), line, col)
            return

        while self._pos < len(self._source) and self._is_id_char(self._peek()):
            value.append(self._advance())

        if not value:
            ch = self._peek()
            # The close-delim's first char (default: `}`) is a legitimate
            # follower of an identifier — don't treat it as unexpected here.
            close_first = self._delims.close_first_char
            if ch and ch not in (close_first, '~', ' ', '\t', '\n', '\r', ')', '|', '='):
                self._advance()
                raise HandlebarsParseError(f'Unexpected character: {ch!r}', line=line, column=col)
            return  # pragma: no cover

        text = ''.join(value)

        if text in ('true', 'false'):
            self._emit(TokenType.BOOLEAN, text, line, col)
        elif text == 'null':
            self._emit(TokenType.NULL, text, line, col)
        elif text == 'undefined':
            self._emit(TokenType.UNDEFINED, text, line, col)
        elif text == 'else':
            self._emit(TokenType.INVERSE, text, line, col)
        elif text == 'as':
            # Check for 'as |'
            saved_pos = self._pos
            saved_line = self._line
            saved_col = self._column
            self._skip_ws()
            if self._pos < len(self._source) and self._peek() == '|':
                self._advance()
                self._emit(TokenType.OPEN_BLOCK_PARAMS, 'as |', line, col)
            else:
                self._pos = saved_pos
                self._line = saved_line
                self._column = saved_col
                self._emit(TokenType.ID, text, line, col)
        else:
            self._emit(TokenType.ID, text, line, col)

    def _read_raw_block(self) -> None:
        """Read a raw block: `{{{{name}}}}...{{{{/name}}}}`.

        Raw blocks are only available with the default delimiters; the
        caller guards on `self._delims.raw_open is not None` before
        dispatching here.
        """
        d = self._delims
        # Caller-guaranteed; narrow for the rest of the function.
        assert d.raw_open is not None
        assert d.raw_close is not None
        open_line = self._line
        open_col = self._column

        # Consume the raw-open delimiter.
        self._advance(len(d.raw_open))
        self._emit(TokenType.OPEN_RAW_BLOCK, d.raw_open, open_line, open_col)

        # Read the helper name
        self._skip_ws()
        name_line, name_col = self._line, self._column
        name_parts: list[str] = []
        while self._pos < len(self._source) and self._is_id_char(self._peek()):
            name_parts.append(self._advance())

        if not name_parts:
            raise HandlebarsParseError('Expected identifier in raw block', line=name_line, column=name_col)

        block_name = ''.join(name_parts)
        self._emit(TokenType.ID, block_name, name_line, name_col)

        self._skip_ws()

        # Expect raw-close
        if not self._starts_with(d.raw_close):
            raise HandlebarsParseError(
                f'Expected {d.raw_close} to close raw block open tag',
                line=self._line,
                column=self._column,
            )

        close_l, close_c = self._line, self._column
        self._advance(len(d.raw_close))
        self._emit(TokenType.CLOSE_RAW_BLOCK, d.raw_close, close_l, close_c)

        # Read raw content until raw-open + '/' + name + raw-close.
        raw_l, raw_c = self._line, self._column
        raw_content: list[str] = []
        end_tag = d.raw_open + '/' + block_name + d.raw_close

        while self._pos < len(self._source):
            if self._starts_with(end_tag):
                break
            raw_content.append(self._advance())

        if not self._starts_with(end_tag):
            raise HandlebarsParseError(f'Unclosed raw block: {block_name}', line=open_line, column=open_col)

        if raw_content:
            self._emit(TokenType.RAW_CONTENT, ''.join(raw_content), raw_l, raw_c)

        end_l, end_c = self._line, self._column
        self._advance(len(end_tag))
        self._emit(TokenType.END_RAW_BLOCK, block_name, end_l, end_c)

    @staticmethod
    def _is_id_char(ch: str) -> bool:
        """Check if a character is valid in an identifier."""
        return ch.isalnum() or ch in ('_', '$', '-')
