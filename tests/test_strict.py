"""Tests for strict mode: raising on missing context references."""

from __future__ import annotations

import pytest

from pydantic_handlebars import (
    HandlebarsEnvironment,
    HandlebarsRuntimeError,
    render,
)

# ---------------------------------------------------------------------------
# Default (non-strict) — behaviour matches Handlebars.js: missing refs render
# as the empty string.
# ---------------------------------------------------------------------------


def test_default_is_non_strict():
    assert render('Hello {{missing}}!') == 'Hello !'


def test_default_env_is_non_strict():
    env = HandlebarsEnvironment()
    assert env.strict is False
    assert env.render('{{missing}}', {}) == ''


# ---------------------------------------------------------------------------
# Strict via the module-level convenience function
# ---------------------------------------------------------------------------


def test_strict_raises_on_missing_top_level():
    with pytest.raises(HandlebarsRuntimeError, match="missing context key 'missing'"):
        render('Hello {{missing}}!', {}, strict=True)


def test_strict_allows_explicit_none():
    # An explicit `None` value is distinct from "key not present" — strict
    # mode lets it through, rendering as the empty string.
    assert render('Hello {{name}}!', {'name': None}, strict=True) == 'Hello !'


def test_strict_passes_when_key_present():
    assert render('Hello {{name}}!', {'name': 'World'}, strict=True) == 'Hello World!'


def test_strict_raises_on_missing_dotted_segment():
    with pytest.raises(HandlebarsRuntimeError, match="missing context key 'email'"):
        render('{{user.email}}', {'user': {'name': 'A'}}, strict=True)


def test_strict_raises_on_missing_root_of_dotted_path():
    with pytest.raises(HandlebarsRuntimeError, match="missing context key 'user'"):
        render('{{user.email}}', {}, strict=True)


def test_strict_allows_explicit_none_intermediate_segment():
    # Same rule as scalars: if the key is present but the value is `None`,
    # subsequent segments resolve to `None` and render as empty.
    assert render('{{user.email}}', {'user': None}, strict=True) == ''


# ---------------------------------------------------------------------------
# Strict via HandlebarsEnvironment
# ---------------------------------------------------------------------------


def test_env_strict_property_reflects_config():
    assert HandlebarsEnvironment(strict=True).strict is True
    assert HandlebarsEnvironment(strict=False).strict is False


def test_env_strict_applies_to_render():
    env = HandlebarsEnvironment(strict=True)
    with pytest.raises(HandlebarsRuntimeError):
        env.render('{{missing}}', {})


def test_env_strict_applies_to_compiled_template():
    env = HandlebarsEnvironment(strict=True)
    template = env.compile('{{missing}}')
    with pytest.raises(HandlebarsRuntimeError):
        template.render({})


# ---------------------------------------------------------------------------
# Block helpers in strict mode
# ---------------------------------------------------------------------------


def test_strict_raises_on_if_with_missing_condition():
    with pytest.raises(HandlebarsRuntimeError, match="missing context key 'maybe'"):
        render('{{#if maybe}}x{{/if}}', {}, strict=True)


def test_strict_allows_if_with_explicit_falsy_condition():
    assert render('{{#if maybe}}x{{else}}y{{/if}}', {'maybe': None}, strict=True) == 'y'
    assert render('{{#if maybe}}x{{else}}y{{/if}}', {'maybe': False}, strict=True) == 'y'


def test_strict_raises_on_each_with_missing_iterable():
    with pytest.raises(HandlebarsRuntimeError, match="missing context key 'items'"):
        render('{{#each items}}x{{/each}}', {}, strict=True)


def test_strict_inside_each_uses_iteration_context():
    # Strict checks inside `each` operate against each item, not the parent.
    template = '{{#each items}}{{name}};{{/each}}'
    assert render(template, {'items': [{'name': 'a'}, {'name': 'b'}]}, strict=True) == 'a;b;'


def test_strict_inside_each_raises_when_item_missing_field():
    template = '{{#each items}}{{name}};{{/each}}'
    with pytest.raises(HandlebarsRuntimeError, match="missing context key 'name'"):
        render(template, {'items': [{'other': 'a'}]}, strict=True)


# ---------------------------------------------------------------------------
# Block parameters: bound names are not subject to strict context lookup.
# ---------------------------------------------------------------------------


def test_strict_block_params_bypass_lookup():
    template = '{{#each items as |item|}}{{item.name}};{{/each}}'
    assert render(template, {'items': [{'name': 'a'}]}, strict=True) == 'a;'


def test_strict_block_params_raise_on_missing_inner_field():
    template = '{{#each items as |item|}}{{item.missing}};{{/each}}'
    with pytest.raises(HandlebarsRuntimeError, match="missing context key 'missing'"):
        render(template, {'items': [{'name': 'a'}]}, strict=True)


# ---------------------------------------------------------------------------
# Data variables (`@index`, etc.) in strict mode
# ---------------------------------------------------------------------------


def test_strict_allows_known_data_variables():
    template = '{{#each items}}{{@index}}:{{name}};{{/each}}'
    assert render(template, {'items': [{'name': 'a'}, {'name': 'b'}]}, strict=True) == '0:a;1:b;'


def test_strict_raises_on_unknown_data_variable():
    with pytest.raises(HandlebarsRuntimeError, match="missing context key 'nope'"):
        render('{{@nope}}', {}, strict=True)


# ---------------------------------------------------------------------------
# Helpers — strict mode applies to helper *arguments*, not helper *names*.
# ---------------------------------------------------------------------------


def test_strict_does_not_apply_to_helper_names():
    # `if` is a registered helper, not a context lookup, so it doesn't
    # fire strict mode even though no field named `if` exists.
    assert render('{{#if value}}x{{/if}}', {'value': True}, strict=True) == 'x'


def test_strict_applies_to_helper_arguments():
    with pytest.raises(HandlebarsRuntimeError, match="missing context key 'missing'"):
        render('{{#if missing}}x{{/if}}', {}, strict=True)


# ---------------------------------------------------------------------------
# `this` and root context references
# ---------------------------------------------------------------------------


def test_strict_passes_for_this():
    # `{{this}}` references the current context object as a whole; strict
    # mode never fires on it.
    env = HandlebarsEnvironment(strict=True)
    assert env.render('{{this}}', 'hello') == 'hello'
    assert env.render('{{this}}', {'k': 'v'}) == "{'k': 'v'}"


def test_strict_passes_for_at_root_field_present():
    template = '{{#each items}}{{@root.top}};{{/each}}'
    assert render(template, {'top': 'T', 'items': [1, 2]}, strict=True) == 'T;T;'


def test_strict_raises_for_at_root_field_missing():
    template = '{{#each items}}{{@root.top}};{{/each}}'
    with pytest.raises(HandlebarsRuntimeError, match="missing context key 'top'"):
        render(template, {'items': [1]}, strict=True)


# ---------------------------------------------------------------------------
# @data parent references (`@../foo`) — strict + non-strict branches
# ---------------------------------------------------------------------------


def test_data_parent_lookup_recurses_through_scopes():
    # Parent-data access (`@../first`): `@first` is set by `each` on
    # the inner scope, so a parent-data lookup at depth 1 from an inner
    # `each` walks back to the outer `each`'s data.
    template = '{{#each outer}}{{#each inner}}{{@../first}};{{/each}}{{/each}}'
    result = render(template, {'outer': [{'inner': [1, 2]}, {'inner': [3]}]})
    # `@first` of the outer each is True at iteration 0, False at 1.
    # Handlebars renders Python bools as lowercase `true`/`false`.
    assert result == 'true;true;false;'


def test_data_parent_lookup_missing_raises_in_strict():
    template = '{{#each items}}{{@../nope}};{{/each}}'
    with pytest.raises(HandlebarsRuntimeError, match="missing context key 'nope'"):
        render(template, {'items': [1]}, strict=True)


def test_data_parent_lookup_missing_returns_empty_non_strict():
    template = '{{#each items}}[{{@../nope}}];{{/each}}'
    assert render(template, {'items': [1, 2]}) == '[];[];'


def test_data_parent_nested_segment_missing_raises_in_strict():
    # Set up a parent data variable that exists but doesn't have the nested
    # field being requested.
    env = HandlebarsEnvironment(strict=True)
    # Hard to construct `@parent.nested.missing` from pure templates;
    # exercise via a custom block helper that injects parent data.
    template = '{{#each items}}{{@../root.missing_field}};{{/each}}'
    with pytest.raises(HandlebarsRuntimeError, match="missing context key 'missing_field'"):
        env.render(template, {'items': [1]})


def test_data_parent_nested_segment_missing_returns_empty_non_strict():
    template = '{{#each items}}[{{@../root.missing_field}}];{{/each}}'
    assert render(template, {'items': [1]}) == '[];'


# ---------------------------------------------------------------------------
# Block-param dotted access in non-strict mode still tolerates missing keys
# ---------------------------------------------------------------------------


def test_block_param_dotted_missing_returns_empty_non_strict():
    template = '{{#each items as |item|}}[{{item.missing}}];{{/each}}'
    assert render(template, {'items': [{'name': 'a'}]}) == '[];'


# ---------------------------------------------------------------------------
# Non-strict `@data` lookups inside nested scopes recurse to parent data
# ---------------------------------------------------------------------------


def test_at_data_lookup_recurses_into_parent_scope_non_strict():
    # Inside the inner `each`, `@first` is not directly in inner.data
    # for the parent's iteration — the lookup recurses through the scope
    # chain. With the inner each at its own iteration, `@first` resolves
    # to the *inner* iteration's flag.
    template = '{{#each outer}}{{#each inner}}{{@first}};{{/each}}{{/each}}'
    assert render(template, {'outer': [{'inner': [1, 2]}, {'inner': [3]}]}) == 'true;false;true;'


def test_at_data_missing_data_var_returns_empty_non_strict():
    # Top-level `{{@nope}}` with no parent scope falls through both
    # `found=False` branches and renders as empty.
    assert render('[{{@nope}}]', {}) == '[]'


def test_at_data_missing_data_var_with_nested_segment_non_strict():
    # `{{@root.nothing}}` — `@root` exists, `nothing` doesn't.
    # Non-strict swallows the missing-segment lookup and renders empty.
    assert render('[{{@root.nothing}}]', {'present': 1}) == '[]'
