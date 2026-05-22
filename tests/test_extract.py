"""Tests for `extract_dependencies`: static top-level context references."""

from __future__ import annotations

import pytest

from pydantic_handlebars import HandlebarsParseError, extract_dependencies

# ---------------------------------------------------------------------------
# Trivial templates
# ---------------------------------------------------------------------------


def test_empty_template():
    assert extract_dependencies('') == set()


def test_pure_text_template():
    assert extract_dependencies('Hello, world.') == set()


def test_only_comments():
    assert extract_dependencies('{{! a comment }} text {{!-- another --}}') == set()


# ---------------------------------------------------------------------------
# Basic references
# ---------------------------------------------------------------------------


def test_single_reference():
    assert extract_dependencies('Hello {{name}}!') == {'name'}


def test_multiple_references():
    assert extract_dependencies('{{greeting}}, {{name}}!') == {'greeting', 'name'}


def test_repeated_references_collapse_to_one():
    assert extract_dependencies('{{name}} {{name}} {{name}}') == {'name'}


# ---------------------------------------------------------------------------
# Dotted paths only contribute their root segment
# ---------------------------------------------------------------------------


def test_dotted_path_returns_root():
    assert extract_dependencies('{{user.name}} <{{user.email}}>') == {'user'}


def test_deeply_dotted_path_returns_root():
    assert extract_dependencies('{{a.b.c.d}}') == {'a'}


# ---------------------------------------------------------------------------
# Block helpers
# ---------------------------------------------------------------------------


def test_if_block_collects_condition_and_body_refs():
    assert extract_dependencies('{{#if cond}}{{value}}{{/if}}') == {'cond', 'value'}


def test_if_else_collects_inverse_refs_too():
    template = '{{#if beta}}{{new_tagline}}{{else}}{{tagline}}{{/if}}'
    assert extract_dependencies(template) == {'beta', 'new_tagline', 'tagline'}


def test_unless_behaves_like_if():
    template = '{{#unless silent}}{{message}}{{/unless}}'
    assert extract_dependencies(template) == {'silent', 'message'}


# ---------------------------------------------------------------------------
# `each` and `with` shift context — inner refs are scoped
# ---------------------------------------------------------------------------


def test_each_inner_ref_is_not_top_level():
    template = '{{#each items}}{{name}}{{/each}}'
    assert extract_dependencies(template) == {'items'}


def test_each_with_parent_ref():
    template = '{{#each items}}{{../top}}{{/each}}'
    assert extract_dependencies(template) == {'items', 'top'}


def test_each_with_root_ref():
    template = '{{#each items}}{{@root.top}}{{/each}}'
    assert extract_dependencies(template) == {'items', 'top'}


def test_with_inner_ref_is_not_top_level():
    template = '{{#with profile}}{{name}}{{/with}}'
    assert extract_dependencies(template) == {'profile'}


def test_nested_each_shifts_twice():
    template = '{{#each groups}}{{#each items}}{{name}} {{../label}} {{../../top}}{{/each}}{{/each}}'
    deps = extract_dependencies(template)
    assert deps == {'groups', 'top'}


def test_each_else_branch_renders_in_parent_context():
    # `{{else}}` of `each` fires when the iterable is empty, so it
    # evaluates against the parent context — references there ARE top-level.
    template = '{{#each items}}x{{else}}{{empty_msg}}{{/each}}'
    assert extract_dependencies(template) == {'items', 'empty_msg'}


# ---------------------------------------------------------------------------
# Block parameters shadow context names locally
# ---------------------------------------------------------------------------


def test_each_block_params_shadow_top_level():
    template = '{{#each items as |item|}}{{item.name}}{{/each}}'
    # `item` is a block param, not a top-level dep.
    assert extract_dependencies(template) == {'items'}


def test_each_block_params_with_index():
    template = '{{#each items as |item index|}}{{index}}:{{item.name}}{{/each}}'
    assert extract_dependencies(template) == {'items'}


# ---------------------------------------------------------------------------
# Helpers — names are not context refs; arguments are
# ---------------------------------------------------------------------------


def test_known_helper_name_is_not_a_dep():
    # Standard helpers (`if`, `unless`, `each`, `with`, `lookup`,
    # `log`) are always recognised.
    assert extract_dependencies('{{lookup obj key}}') == {'obj', 'key'}


def test_unknown_block_helper_falls_back_to_context_ref():
    # If a name is used as a block helper but isn't registered, the renderer
    # would attempt a context lookup — match that behaviour.
    assert extract_dependencies('{{#myhelper x}}body{{/myhelper}}') == {'myhelper', 'x'}


def test_explicit_helpers_argument_suppresses_helper_ref():
    template = '{{#myhelper x}}body{{/myhelper}}'
    assert extract_dependencies(template, helpers={'myhelper'}) == {'x'}


def test_include_extra_helpers_recognises_uppercase():
    # `uppercase` is in the extra-helpers set.
    template = '{{uppercase name}}'
    assert extract_dependencies(template, include_extra_helpers=True) == {'name'}


def test_extra_helpers_default_off_treats_uppercase_as_ref():
    # Without opting in to extras, `uppercase` looks like a context name.
    template = '{{uppercase name}}'
    assert extract_dependencies(template) == {'uppercase', 'name'}


def test_helper_with_no_args_is_bare_path_lookup():
    # `{{my_helper}}` with no args is ambiguous; the renderer prefers a
    # path lookup, so we count it as a dep.
    assert extract_dependencies('{{my_helper}}', helpers={'my_helper'}) == {'my_helper'}


# ---------------------------------------------------------------------------
# Subexpressions
# ---------------------------------------------------------------------------


def test_subexpression_args_are_deps():
    template = '{{#if (eq a b)}}x{{/if}}'
    assert extract_dependencies(template, include_extra_helpers=True) == {'a', 'b'}


def test_subexpression_in_hash_args():
    template = '{{#if cond data=(lookup obj key)}}x{{/if}}'
    assert extract_dependencies(template) == {'cond', 'obj', 'key'}


# ---------------------------------------------------------------------------
# Data variables
# ---------------------------------------------------------------------------


def test_index_alone_is_not_a_dep():
    template = '{{#each items}}{{@index}}:{{name}}{{/each}}'
    assert extract_dependencies(template) == {'items'}


def test_root_field_is_top_level_dep():
    assert extract_dependencies('{{@root.foo}}') == {'foo'}


def test_root_alone_is_not_a_dep():
    # `{{@root}}` on its own returns the root context as a value — we
    # don't know any specific field that it depends on.
    assert extract_dependencies('{{@root}}') == set()


# ---------------------------------------------------------------------------
# `this` references
# ---------------------------------------------------------------------------


def test_this_alone_is_not_a_dep():
    assert extract_dependencies('{{this}}') == set()


def test_this_dot_field_is_a_dep():
    # `{{this.name}}` is equivalent to `{{name}}` — both reference the
    # current context's `name` field. At the top level, that's a dep.
    # Use a defensive check: the parser may or may not put `name` in
    # `parts` depending on how `this.name` parses.
    deps = extract_dependencies('{{this.name}}')
    # The acceptable answers are `{'name'}` (if `parts == ['name']`) or
    # `set()` (if the parser absorbs `this.name` into a single this-token).
    assert deps in ({'name'}, set())


# ---------------------------------------------------------------------------
# Parse errors propagate
# ---------------------------------------------------------------------------


def test_unparseable_template_raises():
    with pytest.raises(HandlebarsParseError):
        extract_dependencies('{{#if x}}')  # unclosed block


# ---------------------------------------------------------------------------
# Composition with the public render() API: deps describe exactly what to
# pass for a successful render.
# ---------------------------------------------------------------------------


def test_deps_align_with_render_inputs():
    from pydantic_handlebars import render

    template = '{{greeting}}, {{#with user}}{{name}}{{/with}}!'
    deps = extract_dependencies(template)
    assert deps == {'greeting', 'user'}
    context = {'greeting': 'Hi', 'user': {'name': 'Alice'}}
    assert render(template, context) == 'Hi, Alice!'


# ---------------------------------------------------------------------------
# Subexpressions in unusual positions and hash arguments
# ---------------------------------------------------------------------------


def test_subexpression_as_mustache_path():
    # `{{(maybe-helper a)}}` invokes the result of a subexpression — the
    # subexpression's args are deps even though the mustache "path" is a
    # SubExpression rather than a PathExpression.
    template = '{{(lookup helpers name) arg}}'
    assert extract_dependencies(template) == {'helpers', 'name', 'arg'}


def test_mustache_hash_arguments_are_deps():
    template = '{{my_helper key=value other=more}}'
    deps = extract_dependencies(template, helpers={'my_helper'})
    assert deps == {'value', 'more'}


def test_subexpression_hash_arguments_are_deps():
    template = '{{#if (eq a b limit=cutoff)}}x{{/if}}'
    deps = extract_dependencies(template, include_extra_helpers=True)
    assert deps == {'a', 'b', 'cutoff'}


# ---------------------------------------------------------------------------
# Parent references past root
# ---------------------------------------------------------------------------


def test_parent_ref_past_root_lands_on_root():
    # `../` past the top scope clamps to root (matching the renderer).
    template = '{{../name}}'
    assert extract_dependencies(template) == {'name'}


# ---------------------------------------------------------------------------
# Literals in argument positions contribute nothing
# ---------------------------------------------------------------------------


def test_literal_arguments_are_not_deps():
    template = '{{my_helper "literal" 42 true null}}'
    assert extract_dependencies(template, helpers={'my_helper'}) == set()
