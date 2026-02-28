"""Tests for custom built-in helpers.

Tests for json, uppercase, lowercase, trim, join, truncate,
eq, ne, gt, gte, lt, lte, and, or, not, default.
"""

from pydantic_handlebars import render

# --- json ---


def test_json_object():
    result = render('{{{json obj}}}', {'obj': {'a': 1}})
    assert result == '{"a": 1}'


def test_json_array():
    result = render('{{json arr}}', {'arr': [1, 2, 3]})
    assert result == '[1, 2, 3]'


def test_json_string():
    result = render('{{json val}}', {'val': 'hello'})
    assert result == '&quot;hello&quot;'


def test_json_string_unescaped():
    result = render('{{{json val}}}', {'val': 'hello'})
    assert result == '"hello"'


# --- uppercase ---


def test_uppercase():
    assert render('{{uppercase val}}', {'val': 'hello'}) == 'HELLO'


def test_uppercase_empty():
    assert render('{{uppercase val}}', {'val': ''}) == ''


# --- lowercase ---


def test_lowercase():
    assert render('{{lowercase val}}', {'val': 'HELLO'}) == 'hello'


# --- trim ---


def test_trim():
    assert render('{{trim val}}', {'val': '  hello  '}) == 'hello'


def test_trim_with_newlines():
    assert render('{{trim val}}', {'val': '\n hello \n'}) == 'hello'


# --- join ---


def test_join_basic():
    assert render('{{join arr ", "}}', {'arr': ['a', 'b', 'c']}) == 'a, b, c'


def test_join_default_separator():
    assert render('{{join arr}}', {'arr': ['a', 'b', 'c']}) == 'a,b,c'


def test_join_empty():
    assert render('{{join arr ", "}}', {'arr': []}) == ''


# --- truncate ---


def test_truncate():
    assert render('{{truncate val 5}}', {'val': 'hello world'}) == 'hello'


def test_truncate_short_string():
    assert render('{{truncate val 100}}', {'val': 'hi'}) == 'hi'


def test_truncate_exact_length():
    assert render('{{truncate val 5}}', {'val': 'hello'}) == 'hello'


# --- eq ---


def test_eq_true():
    assert render('{{#if (eq a b)}}yes{{else}}no{{/if}}', {'a': 1, 'b': 1}) == 'yes'


def test_eq_false():
    assert render('{{#if (eq a b)}}yes{{else}}no{{/if}}', {'a': 1, 'b': 2}) == 'no'


def test_eq_strings():
    assert render('{{#if (eq a b)}}yes{{else}}no{{/if}}', {'a': 'x', 'b': 'x'}) == 'yes'


# --- ne ---


def test_ne_true():
    assert render('{{#if (ne a b)}}yes{{else}}no{{/if}}', {'a': 1, 'b': 2}) == 'yes'


def test_ne_false():
    assert render('{{#if (ne a b)}}yes{{else}}no{{/if}}', {'a': 1, 'b': 1}) == 'no'


# --- gt ---


def test_gt_true():
    assert render('{{#if (gt a b)}}yes{{else}}no{{/if}}', {'a': 2, 'b': 1}) == 'yes'


def test_gt_false():
    assert render('{{#if (gt a b)}}yes{{else}}no{{/if}}', {'a': 1, 'b': 2}) == 'no'


def test_gt_equal():
    assert render('{{#if (gt a b)}}yes{{else}}no{{/if}}', {'a': 1, 'b': 1}) == 'no'


# --- gte ---


def test_gte_true():
    assert render('{{#if (gte a b)}}yes{{else}}no{{/if}}', {'a': 2, 'b': 1}) == 'yes'


def test_gte_equal():
    assert render('{{#if (gte a b)}}yes{{else}}no{{/if}}', {'a': 1, 'b': 1}) == 'yes'


def test_gte_false():
    assert render('{{#if (gte a b)}}yes{{else}}no{{/if}}', {'a': 1, 'b': 2}) == 'no'


# --- lt ---


def test_lt_true():
    assert render('{{#if (lt a b)}}yes{{else}}no{{/if}}', {'a': 1, 'b': 2}) == 'yes'


def test_lt_false():
    assert render('{{#if (lt a b)}}yes{{else}}no{{/if}}', {'a': 2, 'b': 1}) == 'no'


# --- lte ---


def test_lte_true():
    assert render('{{#if (lte a b)}}yes{{else}}no{{/if}}', {'a': 1, 'b': 2}) == 'yes'


def test_lte_equal():
    assert render('{{#if (lte a b)}}yes{{else}}no{{/if}}', {'a': 1, 'b': 1}) == 'yes'


def test_lte_false():
    assert render('{{#if (lte a b)}}yes{{else}}no{{/if}}', {'a': 2, 'b': 1}) == 'no'


# --- and ---


def test_and_both_true():
    assert render('{{#if (and a b)}}yes{{else}}no{{/if}}', {'a': True, 'b': True}) == 'yes'


def test_and_one_false():
    assert render('{{#if (and a b)}}yes{{else}}no{{/if}}', {'a': True, 'b': False}) == 'no'


def test_and_both_false():
    assert render('{{#if (and a b)}}yes{{else}}no{{/if}}', {'a': False, 'b': False}) == 'no'


# --- or ---


def test_or_both_true():
    assert render('{{#if (or a b)}}yes{{else}}no{{/if}}', {'a': True, 'b': True}) == 'yes'


def test_or_one_true():
    assert render('{{#if (or a b)}}yes{{else}}no{{/if}}', {'a': False, 'b': True}) == 'yes'


def test_or_both_false():
    assert render('{{#if (or a b)}}yes{{else}}no{{/if}}', {'a': False, 'b': False}) == 'no'


# --- not ---


def test_not_true():
    assert render('{{#if (not a)}}yes{{else}}no{{/if}}', {'a': False}) == 'yes'


def test_not_false():
    assert render('{{#if (not a)}}yes{{else}}no{{/if}}', {'a': True}) == 'no'


# --- default ---


def test_default_with_value():
    assert render('{{default val "fallback"}}', {'val': 'hello'}) == 'hello'


def test_default_with_falsy():
    assert render('{{default val "fallback"}}', {'val': ''}) == 'fallback'


def test_default_with_none():
    assert render('{{default val "fallback"}}', {'val': None}) == 'fallback'


def test_default_with_zero():
    assert render('{{default val "fallback"}}', {'val': 0}) == 'fallback'
