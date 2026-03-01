"""Tests for custom built-in helpers.

Tests for json, uppercase, lowercase, trim, join, truncate,
eq, ne, gt, gte, lt, lte, and, or, not, default.

These are extra helpers that require ``extra_helpers=True``.
"""

import pytest

from pydantic_handlebars import HandlebarsEnvironment


@pytest.fixture
def env() -> HandlebarsEnvironment:
    return HandlebarsEnvironment(extra_helpers=True)


# --- json ---


def test_json_object(env: HandlebarsEnvironment):
    result = env.render('{{{json obj}}}', {'obj': {'a': 1}})
    assert result == '{"a": 1}'


def test_json_array(env: HandlebarsEnvironment):
    result = env.render('{{json arr}}', {'arr': [1, 2, 3]})
    assert result == '[1, 2, 3]'


def test_json_string(env: HandlebarsEnvironment):
    result = env.render('{{json val}}', {'val': 'hello'})
    assert result == '"hello"'


def test_json_string_unescaped(env: HandlebarsEnvironment):
    result = env.render('{{{json val}}}', {'val': 'hello'})
    assert result == '"hello"'


# --- uppercase ---


def test_uppercase(env: HandlebarsEnvironment):
    assert env.render('{{uppercase val}}', {'val': 'hello'}) == 'HELLO'


def test_uppercase_empty(env: HandlebarsEnvironment):
    assert env.render('{{uppercase val}}', {'val': ''}) == ''


# --- lowercase ---


def test_lowercase(env: HandlebarsEnvironment):
    assert env.render('{{lowercase val}}', {'val': 'HELLO'}) == 'hello'


# --- trim ---


def test_trim(env: HandlebarsEnvironment):
    assert env.render('{{trim val}}', {'val': '  hello  '}) == 'hello'


def test_trim_with_newlines(env: HandlebarsEnvironment):
    assert env.render('{{trim val}}', {'val': '\n hello \n'}) == 'hello'


# --- join ---


def test_join_basic(env: HandlebarsEnvironment):
    assert env.render('{{join arr ", "}}', {'arr': ['a', 'b', 'c']}) == 'a, b, c'


def test_join_default_separator(env: HandlebarsEnvironment):
    assert env.render('{{join arr}}', {'arr': ['a', 'b', 'c']}) == 'a,b,c'


def test_join_empty(env: HandlebarsEnvironment):
    assert env.render('{{join arr ", "}}', {'arr': []}) == ''


# --- truncate ---


def test_truncate(env: HandlebarsEnvironment):
    assert env.render('{{truncate val 5}}', {'val': 'hello world'}) == 'hello'


def test_truncate_short_string(env: HandlebarsEnvironment):
    assert env.render('{{truncate val 100}}', {'val': 'hi'}) == 'hi'


def test_truncate_exact_length(env: HandlebarsEnvironment):
    assert env.render('{{truncate val 5}}', {'val': 'hello'}) == 'hello'


# --- eq ---


def test_eq_true(env: HandlebarsEnvironment):
    assert env.render('{{#if (eq a b)}}yes{{else}}no{{/if}}', {'a': 1, 'b': 1}) == 'yes'


def test_eq_false(env: HandlebarsEnvironment):
    assert env.render('{{#if (eq a b)}}yes{{else}}no{{/if}}', {'a': 1, 'b': 2}) == 'no'


def test_eq_strings(env: HandlebarsEnvironment):
    assert env.render('{{#if (eq a b)}}yes{{else}}no{{/if}}', {'a': 'x', 'b': 'x'}) == 'yes'


# --- ne ---


def test_ne_true(env: HandlebarsEnvironment):
    assert env.render('{{#if (ne a b)}}yes{{else}}no{{/if}}', {'a': 1, 'b': 2}) == 'yes'


def test_ne_false(env: HandlebarsEnvironment):
    assert env.render('{{#if (ne a b)}}yes{{else}}no{{/if}}', {'a': 1, 'b': 1}) == 'no'


# --- gt ---


def test_gt_true(env: HandlebarsEnvironment):
    assert env.render('{{#if (gt a b)}}yes{{else}}no{{/if}}', {'a': 2, 'b': 1}) == 'yes'


def test_gt_false(env: HandlebarsEnvironment):
    assert env.render('{{#if (gt a b)}}yes{{else}}no{{/if}}', {'a': 1, 'b': 2}) == 'no'


def test_gt_equal(env: HandlebarsEnvironment):
    assert env.render('{{#if (gt a b)}}yes{{else}}no{{/if}}', {'a': 1, 'b': 1}) == 'no'


# --- gte ---


def test_gte_true(env: HandlebarsEnvironment):
    assert env.render('{{#if (gte a b)}}yes{{else}}no{{/if}}', {'a': 2, 'b': 1}) == 'yes'


def test_gte_equal(env: HandlebarsEnvironment):
    assert env.render('{{#if (gte a b)}}yes{{else}}no{{/if}}', {'a': 1, 'b': 1}) == 'yes'


def test_gte_false(env: HandlebarsEnvironment):
    assert env.render('{{#if (gte a b)}}yes{{else}}no{{/if}}', {'a': 1, 'b': 2}) == 'no'


# --- lt ---


def test_lt_true(env: HandlebarsEnvironment):
    assert env.render('{{#if (lt a b)}}yes{{else}}no{{/if}}', {'a': 1, 'b': 2}) == 'yes'


def test_lt_false(env: HandlebarsEnvironment):
    assert env.render('{{#if (lt a b)}}yes{{else}}no{{/if}}', {'a': 2, 'b': 1}) == 'no'


# --- lte ---


def test_lte_true(env: HandlebarsEnvironment):
    assert env.render('{{#if (lte a b)}}yes{{else}}no{{/if}}', {'a': 1, 'b': 2}) == 'yes'


def test_lte_equal(env: HandlebarsEnvironment):
    assert env.render('{{#if (lte a b)}}yes{{else}}no{{/if}}', {'a': 1, 'b': 1}) == 'yes'


def test_lte_false(env: HandlebarsEnvironment):
    assert env.render('{{#if (lte a b)}}yes{{else}}no{{/if}}', {'a': 2, 'b': 1}) == 'no'


# --- and ---


def test_and_both_true(env: HandlebarsEnvironment):
    assert env.render('{{#if (and a b)}}yes{{else}}no{{/if}}', {'a': True, 'b': True}) == 'yes'


def test_and_one_false(env: HandlebarsEnvironment):
    assert env.render('{{#if (and a b)}}yes{{else}}no{{/if}}', {'a': True, 'b': False}) == 'no'


def test_and_both_false(env: HandlebarsEnvironment):
    assert env.render('{{#if (and a b)}}yes{{else}}no{{/if}}', {'a': False, 'b': False}) == 'no'


# --- or ---


def test_or_both_true(env: HandlebarsEnvironment):
    assert env.render('{{#if (or a b)}}yes{{else}}no{{/if}}', {'a': True, 'b': True}) == 'yes'


def test_or_one_true(env: HandlebarsEnvironment):
    assert env.render('{{#if (or a b)}}yes{{else}}no{{/if}}', {'a': False, 'b': True}) == 'yes'


def test_or_both_false(env: HandlebarsEnvironment):
    assert env.render('{{#if (or a b)}}yes{{else}}no{{/if}}', {'a': False, 'b': False}) == 'no'


# --- not ---


def test_not_true(env: HandlebarsEnvironment):
    assert env.render('{{#if (not a)}}yes{{else}}no{{/if}}', {'a': False}) == 'yes'


def test_not_false(env: HandlebarsEnvironment):
    assert env.render('{{#if (not a)}}yes{{else}}no{{/if}}', {'a': True}) == 'no'


# --- default ---


def test_default_with_value(env: HandlebarsEnvironment):
    assert env.render('{{default val "fallback"}}', {'val': 'hello'}) == 'hello'


def test_default_with_falsy(env: HandlebarsEnvironment):
    assert env.render('{{default val "fallback"}}', {'val': ''}) == 'fallback'


def test_default_with_none(env: HandlebarsEnvironment):
    assert env.render('{{default val "fallback"}}', {'val': None}) == 'fallback'


def test_default_with_zero(env: HandlebarsEnvironment):
    assert env.render('{{default val "fallback"}}', {'val': 0}) == 'fallback'
