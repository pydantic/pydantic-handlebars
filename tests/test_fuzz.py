"""Fuzz testing for pydantic-handlebars using Hypothesis.

Tests invariants that should hold for ALL inputs — any violation is a bug.

Install:  uv add --group dev hypothesis
Run:      pytest tests/test_fuzz.py -x
Extended: FUZZ_EXTENDED=1 pytest tests/test_fuzz.py -x -s
"""

from __future__ import annotations

import os

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from pydantic_handlebars import (
    HandlebarsEnvironment,
    HandlebarsError,
    HandlebarsParseError,
    SafeString,
    render,
)
from pydantic_handlebars._compiler import Compiler
from pydantic_handlebars._parser import parse
from pydantic_handlebars._tokenizer import tokenize

# ---------------------------------------------------------------------------
# Hypothesis settings — controlled by FUZZ_EXTENDED env var
#
# Default: fast smoke tests for CI (~2s)
# Extended: thorough fuzzing for pre-release confidence (~2-5min, `make fuzz`)
# ---------------------------------------------------------------------------
_extended = bool(os.environ.get('FUZZ_EXTENDED'))

# Most tests: high-volume random input
_base = settings(max_examples=5_000 if _extended else 20, suppress_health_check=[HealthCheck.too_slow])

# Tests with expensive setup or structured generation
_heavy = settings(max_examples=2_000 if _extended else 10, suppress_health_check=[HealthCheck.too_slow])

# Tests that are inherently slow (deep nesting, large output)
_light = settings(max_examples=500 if _extended else 5, suppress_health_check=[HealthCheck.too_slow])

# ---------------------------------------------------------------------------
# Reusable strategies
# ---------------------------------------------------------------------------

# Identifiers that look like handlebars variable names
_identifier = st.from_regex(r'[a-zA-Z_][a-zA-Z0-9_]{0,15}', fullmatch=True)

# Characters likely to trigger edge cases in the tokenizer
_handlebars_alphabet = st.sampled_from(list('{}\\#/^~!>@.|"\' abcdefg012\n\r\t'))

# Template-like strings: biased toward handlebars syntax characters
_template_text = st.text(_handlebars_alphabet, min_size=0, max_size=200)

# Totally arbitrary strings (unicode, control chars, etc.)
_arbitrary_text = st.text(min_size=0, max_size=300)

# JSON-like leaf values for contexts
_leaf_value = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-1_000_000, max_value=1_000_000),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(min_size=0, max_size=50),
)

# Recursive context dicts (limited depth to keep generation fast)
_context_value = st.recursive(
    _leaf_value,
    lambda children: st.one_of(
        st.lists(children, max_size=5),
        st.dictionaries(st.text(min_size=1, max_size=10), children, max_size=5),
    ),
    max_leaves=20,
)

_context = st.dictionaries(
    st.text(min_size=1, max_size=15),
    _context_value,
    max_size=8,
)


# ---------------------------------------------------------------------------
# Strategy: structured Handlebars templates (more likely to parse)
# ---------------------------------------------------------------------------


def _simple_mustache(ident: str) -> str:
    return '{{' + ident + '}}'


def _unescaped_mustache(ident: str) -> str:
    return '{{{' + ident + '}}}'


def _block_each(ident: str, body: str) -> str:
    return '{{#each ' + ident + '}}' + body + '{{/each}}'


def _block_if(ident: str, body: str, else_body: str) -> str:
    if else_body:
        return '{{#if ' + ident + '}}' + body + '{{else}}' + else_body + '{{/if}}'
    return '{{#if ' + ident + '}}' + body + '{{/if}}'


def _block_with(ident: str, body: str) -> str:
    return '{{#with ' + ident + '}}' + body + '{{/with}}'


# Build well-formed templates recursively
_plain_content = st.text(
    alphabet=st.characters(blacklist_characters='{}\\\n\r'),
    min_size=0,
    max_size=30,
)

_well_formed_template = st.recursive(
    # Base cases: plain text or simple mustache
    st.one_of(
        _plain_content,
        _identifier.map(_simple_mustache),
        _identifier.map(_unescaped_mustache),
    ),
    # Recursive cases: blocks containing other templates
    lambda inner: st.one_of(
        # Concatenation of parts
        st.tuples(inner, inner).map(lambda t: t[0] + t[1]),
        # {{#each x}}...{{/each}}
        st.tuples(_identifier, inner).map(lambda t: _block_each(t[0], t[1])),
        # {{#if x}}...{{else}}...{{/if}}
        st.tuples(_identifier, inner, inner).map(lambda t: _block_if(t[0], t[1], t[2])),
        # {{#with x}}...{{/with}}
        st.tuples(_identifier, inner).map(lambda t: _block_with(t[0], t[1])),
    ),
    max_leaves=8,
)


# ===========================================================================
# 1. Core safety: render() must never raise unexpected exceptions
# ===========================================================================


@given(template=_arbitrary_text, ctx=_context)
@_base
def test_render_arbitrary_strings_no_unexpected_exceptions(template: str, ctx: dict[str, object]) -> None:
    """render() should only raise HandlebarsError subclasses, never TypeError/KeyError/etc."""
    try:
        render(template, ctx)
    except HandlebarsError:
        pass


@given(template=_template_text, ctx=_context)
@_base
def test_render_handlebars_like_strings_no_unexpected_exceptions(template: str, ctx: dict[str, object]) -> None:
    """Same as above but with strings biased toward handlebars syntax."""
    try:
        render(template, ctx)
    except HandlebarsError:
        pass


@given(template=_well_formed_template, ctx=_context)
@_heavy
def test_render_well_formed_templates_no_unexpected_exceptions(template: str, ctx: dict[str, object]) -> None:
    """Well-formed templates should render without errors (missing keys produce empty strings)."""
    try:
        render(template, ctx)
    except HandlebarsError:
        pass


# ===========================================================================
# 2. Tokenizer safety
# ===========================================================================


@given(source=_arbitrary_text)
@_base
def test_tokenizer_no_unexpected_exceptions(source: str) -> None:
    """tokenize() should only raise HandlebarsParseError."""
    try:
        tokens = tokenize(source)
        assert len(tokens) > 0  # At least EOF token
    except HandlebarsParseError:
        pass


@given(source=_template_text)
@_base
def test_tokenizer_handlebars_text_no_unexpected_exceptions(source: str) -> None:
    """tokenize() on handlebars-like text should only raise HandlebarsParseError."""
    try:
        tokens = tokenize(source)
        assert len(tokens) > 0
    except HandlebarsParseError:
        pass


# ===========================================================================
# 3. Parser safety
# ===========================================================================


@given(source=_arbitrary_text)
@_base
def test_parser_no_unexpected_exceptions(source: str) -> None:
    """parse() should only raise HandlebarsParseError."""
    try:
        parse(source)
    except HandlebarsParseError:
        pass


@given(source=_template_text)
@_base
def test_parser_handlebars_text_no_unexpected_exceptions(source: str) -> None:
    """parse() on handlebars-like text should only raise HandlebarsParseError."""
    try:
        parse(source)
    except HandlebarsParseError:
        pass


# ===========================================================================
# 4. Property: plain text without {{ renders as itself
# ===========================================================================


@given(
    text=st.text(
        alphabet=st.characters(blacklist_characters='{}\\\n\r'),
        min_size=0,
        max_size=200,
    )
)
@_base
def test_plain_text_renders_as_itself(text: str) -> None:
    """Text with no handlebars delimiters should render unchanged."""
    assert render(text, {}) == text


# ===========================================================================
# 5. Property: render and compile().render() agree
# ===========================================================================


@given(template=_well_formed_template, ctx=_context)
@_heavy
def test_render_matches_compiled_render(template: str, ctx: dict[str, object]) -> None:
    """render(t, c) and compile(t).render(c) should produce the same result."""
    from pydantic_handlebars import compile

    try:
        direct = render(template, ctx)
    except HandlebarsError:
        return

    try:
        compiled = compile(template)
        compiled_result = compiled.render(ctx)
    except HandlebarsError:
        return

    assert direct == compiled_result


# ===========================================================================
# 7. HTML escaping works when enabled (auto_escape=True)
# ===========================================================================

_html_payloads = st.sampled_from(
    [
        '<script>alert(1)</script>',
        '<img onerror=alert(1)>',
        '"><script>x</script>',
        "'-alert(1)-'",
        '<svg onload=alert(1)>',
    ]
)

_escape_env = HandlebarsEnvironment(auto_escape=True)


@given(payload=_html_payloads)
@_base
def test_html_escaped_when_auto_escape_enabled(payload: str) -> None:
    """HTML special characters are escaped in {{expr}} output when auto_escape=True."""
    result = _escape_env.render('{{val}}', {'val': payload})
    assert '<' not in result
    assert '>' not in result


@given(value=st.text(min_size=1, max_size=100))
@_base
def test_double_mustache_no_raw_angle_brackets_when_auto_escape(value: str) -> None:
    """{{expr}} output should not contain literal < or > when auto_escape=True."""
    result = _escape_env.render('{{val}}', {'val': value})
    if '<' in value:
        assert '<' not in result
    if '>' in value:
        assert '>' not in result


@given(value=st.text(min_size=1, max_size=100))
@_base
def test_double_mustache_preserves_content_by_default(value: str) -> None:
    """{{expr}} output preserves raw content when auto_escape=False (default)."""
    result = render('{{val}}', {'val': value})
    assert result == value


@given(value=st.text(min_size=1, max_size=100))
@_base
def test_triple_mustache_preserves_raw_content(value: str) -> None:
    """{{{expr}}} should output content without escaping."""
    result = render('{{{val}}}', {'val': value})
    assert result == value


# ===========================================================================
# 8. Resource limits: deeply nested templates terminate
# ===========================================================================


@given(depth=st.integers(min_value=50, max_value=200))
@_light
def test_deep_nesting_terminates(depth: int) -> None:
    """Deeply nested blocks should hit the depth limit, not stack overflow."""
    template = '{{#if x}}' * depth + 'deep' + '{{/if}}' * depth
    try:
        render(template, {'x': True})
    except HandlebarsError:
        pass  # Depth limit error is expected


@given(count=st.integers(min_value=100, max_value=500))
@_light
def test_large_repeated_output_terminates(count: int) -> None:
    """Repeated expansion should be bounded by output size limits."""
    big_value = 'x' * 1000
    items = list(range(count))
    try:
        render('{{#each items}}' + big_value + '{{/each}}', {'items': items})
    except HandlebarsError:
        pass


# ===========================================================================
# 9. Each/with block helpers: random iteration
# ===========================================================================


@given(items=st.lists(st.text(min_size=0, max_size=20), max_size=20))
@_base
def test_each_over_random_lists(items: list[str]) -> None:
    """{{#each}} should handle lists of any string values without crashing."""
    result = render('{{#each items}}|{{this}}|{{/each}}', {'items': items})
    assert isinstance(result, str)
    if not items:
        assert result == ''


@given(data=st.dictionaries(st.text(min_size=1, max_size=10), st.text(min_size=0, max_size=20), max_size=10))
@_base
def test_each_over_random_dicts(data: dict[str, str]) -> None:
    """{{#each}} should handle dicts of any string key/value pairs without crashing."""
    result = render('{{#each data}}{{@key}}\n{{/each}}', {'data': data})
    assert isinstance(result, str)
    if not data:
        assert result == ''


@given(ctx=_context)
@_base
def test_with_random_context(ctx: dict[str, object]) -> None:
    """{{#with}} should handle arbitrary context objects."""
    try:
        render('{{#with ctx}}{{this}}{{/with}}', {'ctx': ctx})
    except HandlebarsError:
        pass


# ===========================================================================
# 10. Escaped mustache syntax
# ===========================================================================


@given(ident=_identifier)
@_base
def test_escaped_mustaches_render_literally(ident: str) -> None:
    r"""\\{{ should render as literal {{ text."""
    template = '\\{{' + ident + '}}'
    result = render(template, {ident: 'SHOULD_NOT_APPEAR'})
    assert 'SHOULD_NOT_APPEAR' not in result


# ===========================================================================
# 11. Comment stripping
# ===========================================================================


@given(
    comment_text=st.text(
        alphabet=st.characters(blacklist_characters='{}'),
        min_size=0,
        max_size=50,
    )
)
@_base
def test_comments_never_appear_in_output(comment_text: str) -> None:
    """{{! comment }} content should be fully stripped from output."""
    marker = '\x00MARKER\x00'
    template = marker + '{{!-- ' + comment_text + ' --}}' + marker
    result = render(template, {})
    assert result == marker + marker


# ===========================================================================
# 12. SafeString bypass
# ===========================================================================


@given(html=st.text(min_size=1, max_size=100))
@_base
def test_safestring_serialized_to_str(html: str) -> None:
    """SafeString in context is serialized to plain str.

    With auto_escape=False (default), the content renders as-is.
    With auto_escape=True, the serialized str gets HTML-escaped.
    """
    safe = SafeString(html)

    # Default (auto_escape=False): no escaping
    result = render('{{val}}', {'val': safe})
    assert result == html

    # Explicit auto_escape=True: serialized to str, so escaping applies
    result_escaped = _escape_env.render('{{val}}', {'val': safe})
    if '<' in html:
        assert '<' not in result_escaped
    if '>' in html:
        assert '>' not in result_escaped


# ===========================================================================
# 13. Numeric and boolean rendering
# ===========================================================================


@given(n=st.integers(min_value=-1_000_000, max_value=1_000_000))
@_base
def test_integer_rendering(n: int) -> None:
    result = render('{{val}}', {'val': n})
    assert result == str(n)


@given(n=st.floats(allow_nan=False, allow_infinity=False, min_value=-1e6, max_value=1e6))
@_base
def test_float_rendering(n: float) -> None:
    result = render('{{val}}', {'val': n})
    assert result == str(n)


@given(b=st.booleans())
@_base
def test_boolean_rendering(b: bool) -> None:
    result = render('{{val}}', {'val': b})
    assert result == ('true' if b else 'false')


def test_none_rendering() -> None:
    result = render('{{val}}', {'val': None})
    assert result == ''


# ===========================================================================
# 14. Stress: many variables in one template
# ===========================================================================


@given(
    data=st.fixed_dictionaries(
        {}, optional={chr(c): st.text(min_size=1, max_size=10) for c in range(ord('a'), ord('z') + 1)}
    )
)
@_heavy
def test_many_variables(data: dict[str, str]) -> None:
    """Templates with many variable references should work correctly."""
    parts = [f'{{{{{k}}}}}' for k in data]
    template = ' '.join(parts)
    result = render(template, data)
    assert isinstance(result, str)


# ===========================================================================
# 15. Compiler directly with constrained limits
# ===========================================================================


@given(template=_well_formed_template, ctx=_context)
@_heavy
def test_compiler_with_tight_limits(template: str, ctx: dict[str, object]) -> None:
    """Compiler with very tight limits should raise HandlebarsRuntimeError, not crash."""
    try:
        program = parse(template)
    except HandlebarsParseError:
        return

    compiler = Compiler(helpers={}, max_depth=5, max_output_size=1024)
    try:
        compiler.render(program, ctx)
    except HandlebarsError:
        pass


# ===========================================================================
# 16. Pathological input patterns
# ===========================================================================


@given(n=st.integers(min_value=1, max_value=500))
@_light
def test_many_open_braces(n: int) -> None:
    """Lots of {{ without closing should parse-error, not hang or crash."""
    template = '{{' * n
    try:
        render(template, {})
    except HandlebarsError:
        pass


@given(n=st.integers(min_value=1, max_value=500))
@_light
def test_many_close_braces(n: int) -> None:
    """Lots of }} without opening should be treated as content."""
    template = '}}' * n
    try:
        render(template, {})
    except HandlebarsError:
        pass


@given(n=st.integers(min_value=1, max_value=200))
@_light
def test_alternating_braces(n: int) -> None:
    template = '{}'.join([''] * n) + '}'.join([''] * n)
    try:
        render(template, {})
    except HandlebarsError:
        pass


@given(n=st.integers(min_value=1, max_value=100))
@_light
def test_nested_subexpressions(n: int) -> None:
    """Deeply nested subexpressions like (helper (helper (helper x)))."""
    inner = 'x'
    for _ in range(n):
        inner = f'(lookup {inner})'
    template = '{{' + inner + '}}'
    try:
        render(template, {'x': 'val'})
    except HandlebarsError:
        pass


@given(n=st.integers(min_value=1, max_value=100))
@_light
def test_many_parent_refs(n: int) -> None:
    """Paths with many ../ segments should not crash."""
    path = '../' * n + 'x'
    template = '{{#with a}}{{' + path + '}}{{/with}}'
    try:
        render(template, {'a': {}, 'x': 'found'})
    except HandlebarsError:
        pass


# ===========================================================================
# 17. Context with unusual types
# ===========================================================================


@given(data=st.data())
@_heavy
def test_unusual_context_values(data: st.DataObject) -> None:
    """render() should handle unusual Python types in context without crashing.

    Non-serializable types raise HandlebarsError (via serialization).
    """
    unusual_value = data.draw(
        st.one_of(
            st.just(frozenset({0})),
            st.just(b'bytes'),
            st.just({0}),
            st.just(()),
            st.just(range(10)),
            st.builds(
                complex,
                st.floats(allow_nan=False, allow_infinity=False),
                st.floats(allow_nan=False, allow_infinity=False),
            ),
        )
    )
    try:
        render('{{val}}', {'val': unusual_value})
    except HandlebarsError:
        pass


# ===========================================================================
# 18. Context keys that look like attacks
# ===========================================================================


@given(
    key=st.one_of(
        st.from_regex(r'__[a-z]{1,10}__', fullmatch=True),
        st.just('constructor'),
        st.just('__proto__'),
        st.just('prototype'),
    ),
)
@_base
def test_suspicious_context_keys(key: str) -> None:
    """Suspicious keys are now normal dict keys (context is pre-serialized)."""
    try:
        result = render('{{' + key + '}}', {key: 'VALUE'})
        # All keys, including dunder keys, should now render their values
        assert result == 'VALUE'
    except HandlebarsError:
        pass


# ===========================================================================
# 19. Whitespace control fuzz
# ===========================================================================


@given(
    content_before=_plain_content,
    content_after=_plain_content,
    ident=_identifier,
    strip_open=st.booleans(),
    strip_close=st.booleans(),
)
@_heavy
def test_whitespace_control_does_not_crash(
    content_before: str, content_after: str, ident: str, strip_open: bool, strip_close: bool
) -> None:
    """Whitespace strip markers (~) should never cause crashes."""
    open_strip = '~' if strip_open else ''
    close_strip = '~' if strip_close else ''
    template = content_before + '{{' + open_strip + ident + close_strip + '}}' + content_after
    try:
        render(template, {ident: 'val'})
    except HandlebarsError:
        pass


# ===========================================================================
# 20. Hash arguments fuzz
# ===========================================================================


@given(
    helper_name=_identifier,
    key=_identifier,
    value=st.text(min_size=0, max_size=20),
)
@_heavy
def test_hash_arguments_do_not_crash(helper_name: str, key: str, value: str) -> None:
    """Hash arguments (key=value) should not crash even for unknown helpers."""
    escaped_value = value.replace('"', '\\"')
    template = '{{' + helper_name + ' ' + key + '="' + escaped_value + '"}}'
    try:
        render(template, {})
    except HandlebarsError:
        pass
