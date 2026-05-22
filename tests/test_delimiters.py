"""Tests for configurable mustache delimiters.

The default `{{` / `}}` pair is exercised by the rest of the suite. These
tests pin down the behaviour with custom delimiter pairs — primarily `@{`
/ `}@`, which is what calling code (e.g. Pydantic Logfire's managed-
variable composition) uses to embed a second rendering pass without
fighting the regular `{{...}}` runtime placeholders.
"""

from __future__ import annotations

import pytest

from pydantic_handlebars import (
    HandlebarsEnvironment,
    HandlebarsParseError,
    HandlebarsRuntimeError,
    extract_dependencies,
    render,
)

# ---------------------------------------------------------------------------
# Default behaviour preserved
# ---------------------------------------------------------------------------


def test_module_render_defaults_match_handlebars_spec():
    assert render('Hello {{name}}!', {'name': 'World'}) == 'Hello World!'


def test_env_defaults_to_braces():
    env = HandlebarsEnvironment()
    assert env.open_delim == '{{'
    assert env.close_delim == '}}'


# ---------------------------------------------------------------------------
# Basic rendering with `@{` / `}@`
# ---------------------------------------------------------------------------


def test_basic_render_with_at_brace_delimiters():
    result = render('Hello @{name}@!', {'name': 'World'}, open_delim='@{', close_delim='}@')
    assert result == 'Hello World!'


def test_dotted_path_with_custom_delims():
    result = render('@{user.name}@', {'user': {'name': 'A'}}, open_delim='@{', close_delim='}@')
    assert result == 'A'


def test_helper_invocation_with_custom_delims():
    result = render('@{lookup obj key}@', {'obj': {'k': 'V'}, 'key': 'k'}, open_delim='@{', close_delim='}@')
    assert result == 'V'


def test_repeated_references_with_custom_delims():
    template = '@{a}@ + @{a}@ = @{a}@@{a}@'
    result = render(template, {'a': 'x'}, open_delim='@{', close_delim='}@')
    assert result == 'x + x = xx'


def test_render_returns_empty_for_missing_reference():
    # Same as default behaviour when not in strict mode.
    result = render('@{missing}@', {}, open_delim='@{', close_delim='}@')
    assert result == ''


# ---------------------------------------------------------------------------
# Block helpers under custom delimiters
# ---------------------------------------------------------------------------


def test_if_block_with_custom_delims():
    template = '@{#if beta}@new@{else}@@{tagline}@@{/if}@'
    assert render(template, {'beta': False, 'tagline': 'classic'}, open_delim='@{', close_delim='}@') == 'classic'
    assert render(template, {'beta': True, 'tagline': 'classic'}, open_delim='@{', close_delim='}@') == 'new'


def test_each_block_with_custom_delims():
    template = '@{#each items}@@{name}@;@{/each}@'
    result = render(
        template,
        {'items': [{'name': 'a'}, {'name': 'b'}]},
        open_delim='@{',
        close_delim='}@',
    )
    assert result == 'a;b;'


def test_each_with_parent_ref_under_custom_delims():
    template = '@{#each items}@@{../top}@:@{name}@;@{/each}@'
    result = render(
        template,
        {'top': 'T', 'items': [{'name': 'a'}, {'name': 'b'}]},
        open_delim='@{',
        close_delim='}@',
    )
    assert result == 'T:a;T:b;'


def test_with_block_under_custom_delims():
    template = '@{#with profile}@@{name}@@{/with}@'
    result = render(template, {'profile': {'name': 'Z'}}, open_delim='@{', close_delim='}@')
    assert result == 'Z'


def test_unless_block_under_custom_delims():
    template = '@{#unless silent}@@{message}@@{/unless}@'
    assert render(template, {'silent': False, 'message': 'hi'}, open_delim='@{', close_delim='}@') == 'hi'
    assert render(template, {'silent': True, 'message': 'hi'}, open_delim='@{', close_delim='}@') == ''


# ---------------------------------------------------------------------------
# `{{...}}` is plain content when delimiters are `@{...}@` and vice versa
# ---------------------------------------------------------------------------


def test_default_delims_treated_as_content_when_custom_is_active():
    # The whole point of configurable delimiters: a composition pass can
    # use `@{...}@` while leaving `{{...}}` placeholders untouched for a
    # later rendering pass.
    template = 'Hi @{name}@, see {{user}} later'
    result = render(template, {'name': 'A'}, open_delim='@{', close_delim='}@')
    assert result == 'Hi A, see {{user}} later'


def test_custom_delims_treated_as_content_when_default_is_active():
    template = 'literal @{name}@ and rendered {{name}}'
    result = render(template, {'name': 'X'})
    assert result == 'literal @{name}@ and rendered X'


# ---------------------------------------------------------------------------
# Triple-stache and raw blocks are default-only
# ---------------------------------------------------------------------------


def test_triple_stache_treated_as_content_with_custom_delims():
    # `@{{name}}@` under `@{`/`}@` delimiters tokenises as OPEN `@{` ID `{name}`
    # CLOSE `}@`. The body `{name}` isn't a valid identifier — so the parser
    # rejects it. That's the right outcome: triple-stache has no extension
    # for non-default delimiters.
    with pytest.raises(HandlebarsParseError):
        render('@{{name}}@', {'name': 'X'}, open_delim='@{', close_delim='}@')


def test_default_delims_still_support_triple_stache():
    # `{{{value}}}` renders unescaped under the default delims.
    env = HandlebarsEnvironment(auto_escape=True)
    assert env.render('{{value}}', {'value': '<x>'}) == '&lt;x&gt;'
    assert env.render('{{{value}}}', {'value': '<x>'}) == '<x>'


def test_default_delims_still_support_raw_blocks():
    # `{{{{raw}}}}...{{{{/raw}}}}` preserves its body verbatim.
    template = '{{{{raw}}}}{{value}}{{{{/raw}}}}'
    assert render(template, {'value': 'ignored'}) == '{{value}}'


# ---------------------------------------------------------------------------
# Per-expression escape opt-out via the `&` variant works under custom delims.
# Triple-stache has no analogue, but `@{&name}@` does.
# ---------------------------------------------------------------------------


def test_amp_unescape_under_custom_delims():
    # With auto_escape on, the default form escapes...
    env = HandlebarsEnvironment(auto_escape=True, open_delim='@{', close_delim='}@')
    unsafe = {'value': '<script>X</script>'}
    assert env.render('@{value}@', unsafe) == '&lt;script&gt;X&lt;/script&gt;'
    # ...but the ampersand-unescape variant lets a single expression opt out:
    assert env.render('@{&value}@', unsafe) == '<script>X</script>'


def test_amp_unescape_under_default_delims_still_works():
    # Regression guard: the parser fix used to hard-code `'{{&'`.
    env = HandlebarsEnvironment(auto_escape=True)
    assert env.render('{{&value}}', {'value': '<x>'}) == '<x>'


# ---------------------------------------------------------------------------
# Escape sequence under custom delimiters
# ---------------------------------------------------------------------------


def test_escape_sequence_with_custom_delims():
    # `\@{name}@` should produce literal `@{name}@`.
    template = '\\@{name}@ then @{name}@'
    result = render(template, {'name': 'X'}, open_delim='@{', close_delim='}@')
    assert result == '@{name}@ then X'


# ---------------------------------------------------------------------------
# Comments under custom delimiters
# ---------------------------------------------------------------------------


def test_short_comment_with_custom_delims():
    template = '@{! a comment }@hello'
    assert render(template, {}, open_delim='@{', close_delim='}@') == 'hello'


def test_long_comment_with_custom_delims():
    template = '@{!-- multi line\ncomment --}@hello'
    assert render(template, {}, open_delim='@{', close_delim='}@') == 'hello'


# ---------------------------------------------------------------------------
# Whitespace control (`~`) under custom delimiters
# ---------------------------------------------------------------------------


def test_open_strip_with_custom_delims():
    template = 'before  @{~name}@after'
    assert render(template, {'name': 'X'}, open_delim='@{', close_delim='}@') == 'beforeXafter'


def test_close_strip_with_custom_delims():
    template = 'before@{name~}@  after'
    assert render(template, {'name': 'X'}, open_delim='@{', close_delim='}@') == 'beforeXafter'


# ---------------------------------------------------------------------------
# Environment-level configuration
# ---------------------------------------------------------------------------


def test_env_exposes_custom_delimiters_as_properties():
    env = HandlebarsEnvironment(open_delim='@{', close_delim='}@')
    assert env.open_delim == '@{'
    assert env.close_delim == '}@'


def test_env_render_uses_configured_delimiters():
    env = HandlebarsEnvironment(open_delim='@{', close_delim='}@')
    assert env.render('@{x}@', {'x': 'v'}) == 'v'


def test_env_compile_carries_delimiters_into_compiled_template():
    env = HandlebarsEnvironment(open_delim='@{', close_delim='}@')
    template = env.compile('@{x}@')
    assert template.render({'x': 'v'}) == 'v'


# ---------------------------------------------------------------------------
# Validation: invalid delimiter pairs
# ---------------------------------------------------------------------------


def test_empty_open_delim_rejected():
    with pytest.raises(ValueError, match='non-empty'):
        render('hello', {}, open_delim='', close_delim='}}')


def test_empty_close_delim_rejected():
    with pytest.raises(ValueError, match='non-empty'):
        render('hello', {}, open_delim='{{', close_delim='')


def test_identical_open_and_close_rejected():
    with pytest.raises(ValueError, match='must differ'):
        render('hello', {}, open_delim='::', close_delim='::')


def test_whitespace_prefixed_open_rejected():
    with pytest.raises(ValueError, match='whitespace'):
        render('hello', {}, open_delim=' {', close_delim='}}')


def test_whitespace_suffixed_close_rejected():
    with pytest.raises(ValueError, match='whitespace'):
        render('hello', {}, open_delim='{{', close_delim='} ')


@pytest.mark.parametrize('bad_char', list('"\'()=|~'))
def test_open_delim_with_forbidden_chars_rejected(bad_char: str):
    with pytest.raises(ValueError, match='open_delim must not contain'):
        render('hello', {}, open_delim=bad_char + '{', close_delim='}}')


@pytest.mark.parametrize('bad_char', list('"\'()=|~'))
def test_close_delim_with_forbidden_chars_rejected(bad_char: str):
    with pytest.raises(ValueError, match='close_delim must not contain'):
        render('hello', {}, open_delim='{{', close_delim='}' + bad_char)


# ---------------------------------------------------------------------------
# `extract_dependencies` with custom delimiters
# ---------------------------------------------------------------------------


def test_extract_dependencies_with_custom_delims():
    deps = extract_dependencies(
        '@{#each items}@@{name}@@{/each}@@{outer}@',
        open_delim='@{',
        close_delim='}@',
    )
    assert deps == {'items', 'outer'}


def test_extract_dependencies_treats_default_delim_content_as_literal():
    # Under `@{`/`}@`, anything written as `{{x}}` is plain text and
    # contributes no dependency.
    deps = extract_dependencies('@{a}@ and {{b}}', open_delim='@{', close_delim='}@')
    assert deps == {'a'}


def test_extract_dependencies_dotted_path_with_custom_delims():
    deps = extract_dependencies('@{user.name}@ <@{user.email}@>', open_delim='@{', close_delim='}@')
    assert deps == {'user'}


# ---------------------------------------------------------------------------
# Strict mode + custom delimiters compose
# ---------------------------------------------------------------------------


def test_strict_with_custom_delims_raises_on_missing():
    with pytest.raises(HandlebarsRuntimeError, match="missing context key 'name'"):
        render('@{name}@', {}, strict=True, open_delim='@{', close_delim='}@')


def test_strict_with_custom_delims_passes_when_present():
    assert render('@{name}@', {'name': 'X'}, strict=True, open_delim='@{', close_delim='}@') == 'X'


# ---------------------------------------------------------------------------
# Composition use case: two-pass rendering preserving inner placeholders
# ---------------------------------------------------------------------------


def test_composition_then_render_two_pass_round_trip():
    # First pass: compose with `@{...}@` (e.g. logfire's variable composition)
    # leaves `{{...}}` placeholders untouched.
    first_pass_template = 'You are helping @{role}@. Greet {{user_name}}.'
    after_composition = render(
        first_pass_template,
        {'role': 'a designer'},
        open_delim='@{',
        close_delim='}@',
    )
    assert after_composition == 'You are helping a designer. Greet {{user_name}}.'

    # Second pass: render the remaining `{{...}}` with runtime inputs.
    final = render(after_composition, {'user_name': 'Alice'})
    assert final == 'You are helping a designer. Greet Alice.'
