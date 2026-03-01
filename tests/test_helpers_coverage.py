"""Tests to cover missing lines in _helpers.py.

Focuses on edge cases: no-arg subexpressions, empty collections,
lookup edge cases, log helper, comparison/boolean helpers with
insufficient args, and default helper edge cases.
"""

# pyright: reportUnknownLambdaType=false, reportUnknownArgumentType=false

import pytest

from pydantic_handlebars import HandlebarsEnvironment, render

_extra_env = HandlebarsEnvironment(extra_helpers=True)

# --- _helper_if: line 25 (condition = context when args is empty) ---


class TestIfNoArgs:
    def test_if_no_explicit_arg_truthy_context(self):
        """When #if is used without an argument, the context itself is the condition.

        In block helper dispatch, the call is helper(scope.context, *args, options=options).
        With no params, args is empty so condition = context (line 25).
        We need a truthy context.
        """
        # {{#if}} with no param means condition = context (the current scope context)
        # The context dict is truthy (it's not empty), so the block should render.
        # But actually the dict context is the whole dict, and is_falsy returns False for dicts.
        result = render('{{#if}}yes{{else}}no{{/if}}', {'some': 'data'})
        assert result == 'yes'

    def test_if_no_explicit_arg_falsy_context(self):
        """When #if has no arg and context itself is falsy.

        We use #each to iterate over an array containing a falsy value (0),
        which sets the loop context to that value. Then #if with no arg
        uses the context (0) as the condition.
        """
        result = render('{{#each items}}{{#if}}yes{{else}}no{{/if}}{{/each}}', {'items': [0]})
        assert result == 'no'


# --- _helper_unless: lines 41, 44 ---


class TestUnlessNoArgs:
    def test_unless_no_explicit_arg_truthy_context(self):
        """Unless with no args uses context as condition (line 41)."""
        result = render('{{#unless}}yes{{else}}no{{/unless}}', {'some': 'data'})
        assert result == 'no'

    def test_unless_no_explicit_arg_falsy_context(self):
        """Unless with no args, context is falsy (0). Use #each to set context."""
        result = render('{{#each items}}{{#unless}}yes{{else}}no{{/unless}}{{/each}}', {'items': [0]})
        assert result == 'yes'


# --- _helper_each: line 67 (empty dict) ---


class TestEachEmptyDict:
    def test_each_empty_dict_inverse(self):
        """Iterating over an empty dict should render the inverse/else block."""
        result = render('{{#each obj}}{{@key}}:{{this}}{{else}}empty{{/each}}', {'obj': {}})
        assert result == 'empty'


# --- _helper_lookup: lines 116, 133-144 ---


class TestLookupEdgeCases:
    def test_lookup_no_args(self):
        """Lookup with fewer than 2 args returns None (line 116).

        We use a subexpression to call lookup with only 1 arg.
        """
        result = render('{{#if (lookup obj)}}found{{else}}empty{{/if}}', {'obj': {'a': 1}})
        assert result == 'empty'

    def test_lookup_list_invalid_key(self):
        """Lookup on a list with a non-integer key (lines 133-134)."""
        result = render('{{lookup arr "notanumber"}}', {'arr': ['a', 'b', 'c']})
        assert result == ''

    def test_lookup_list_out_of_bounds(self):
        """Lookup on a list with an out-of-bounds index (line 135)."""
        result = render('{{lookup arr 99}}', {'arr': ['a', 'b', 'c']})
        assert result == ''

    def test_lookup_on_string_returns_empty(self):
        """Lookup on a string (non-dict/non-list) returns empty."""
        result = render('{{lookup obj "key"}}', {'obj': 'hello'})
        assert result == ''

    def test_lookup_on_number_returns_empty(self):
        """Lookup on a number (non-dict/non-list) returns empty."""
        result = render('{{lookup obj 0}}', {'obj': 42})
        assert result == ''

    def test_lookup_null_object(self):
        """Lookup on null object returns empty (line 121, already tested but ensuring)."""
        result = render('{{lookup obj "key"}}', {'obj': None})
        assert result == ''


# --- _helper_log: lines 152-155 ---


class TestLogHelper:
    def test_log_basic(self):
        """Log helper emits a UserWarning (lines 152-155)."""
        with pytest.warns(UserWarning, match=r'\[Handlebars info\] hello'):
            render('{{log "hello"}}', {})

    def test_log_with_level(self):
        """Log helper with explicit level hash arg."""
        with pytest.warns(UserWarning, match=r'\[Handlebars warn\] test message'):
            render('{{log "test message" level="warn"}}', {})

    def test_log_multiple_args(self):
        """Log helper with multiple arguments joined by space."""
        with pytest.warns(UserWarning, match=r'\[Handlebars info\] hello world'):
            render('{{log "hello" "world"}}', {})

    def test_log_returns_empty(self):
        """Log helper returns empty string so it produces no output."""
        with pytest.warns(UserWarning):
            result = render('before{{log "msg"}}after', {})
        assert result == 'beforeafter'


# --- Custom helpers with no args via subexpressions: lines 164, 171, 178, 185, 192, 198, 204 ---


class TestCustomHelpersNoArgs:
    def test_json_no_args(self):
        """json with no args returns '' (line 164)."""
        result = _extra_env.render('{{#if (json)}}yes{{else}}no{{/if}}', {})
        assert result == 'no'

    def test_uppercase_no_args(self):
        """uppercase with no args returns '' (line 171)."""
        result = _extra_env.render('{{#if (uppercase)}}yes{{else}}no{{/if}}', {})
        assert result == 'no'

    def test_lowercase_no_args(self):
        """lowercase with no args returns '' (line 178)."""
        result = _extra_env.render('{{#if (lowercase)}}yes{{else}}no{{/if}}', {})
        assert result == 'no'

    def test_trim_no_args(self):
        """trim with no args returns '' (line 185)."""
        result = _extra_env.render('{{#if (trim)}}yes{{else}}no{{/if}}', {})
        assert result == 'no'

    def test_join_no_args(self):
        """join with no args returns '' (line 192)."""
        result = _extra_env.render('{{#if (join)}}yes{{else}}no{{/if}}', {})
        assert result == 'no'

    def test_join_non_list_arg(self):
        """join with a non-list argument returns to_string of it (line 198)."""
        result = _extra_env.render('{{join val}}', {'val': 'hello'})
        assert result == 'hello'

    def test_truncate_no_args(self):
        """truncate with no args returns '' (line 204)."""
        result = _extra_env.render('{{#if (truncate)}}yes{{else}}no{{/if}}', {})
        assert result == 'no'


# --- Comparison helpers with < 2 args: lines 215, 222, 229, 236, 243, 250 ---


class TestComparisonHelpersInsufficientArgs:
    def test_eq_no_args(self):
        """eq with no args returns False (line 215)."""
        result = _extra_env.render('{{#if (eq)}}yes{{else}}no{{/if}}', {})
        assert result == 'no'

    def test_ne_no_args(self):
        """ne with no args returns True (line 222)."""
        result = _extra_env.render('{{#if (ne)}}yes{{else}}no{{/if}}', {})
        assert result == 'yes'

    def test_gt_no_args(self):
        """gt with no args returns False (line 229)."""
        result = _extra_env.render('{{#if (gt)}}yes{{else}}no{{/if}}', {})
        assert result == 'no'

    def test_gte_no_args(self):
        """gte with no args returns False (line 236)."""
        result = _extra_env.render('{{#if (gte)}}yes{{else}}no{{/if}}', {})
        assert result == 'no'

    def test_lt_no_args(self):
        """lt with no args returns False (line 243)."""
        result = _extra_env.render('{{#if (lt)}}yes{{else}}no{{/if}}', {})
        assert result == 'no'

    def test_lte_no_args(self):
        """lte with no args returns False (line 250)."""
        result = _extra_env.render('{{#if (lte)}}yes{{else}}no{{/if}}', {})
        assert result == 'no'

    def test_eq_one_arg(self):
        """eq with only 1 arg returns False (line 215)."""
        result = _extra_env.render('{{#if (eq a)}}yes{{else}}no{{/if}}', {'a': 1})
        assert result == 'no'

    def test_ne_one_arg(self):
        """ne with only 1 arg returns True (line 222)."""
        result = _extra_env.render('{{#if (ne a)}}yes{{else}}no{{/if}}', {'a': 1})
        assert result == 'yes'

    def test_gt_one_arg(self):
        """gt with only 1 arg returns False (line 229)."""
        result = _extra_env.render('{{#if (gt a)}}yes{{else}}no{{/if}}', {'a': 5})
        assert result == 'no'

    def test_gte_one_arg(self):
        """gte with only 1 arg returns False (line 236)."""
        result = _extra_env.render('{{#if (gte a)}}yes{{else}}no{{/if}}', {'a': 5})
        assert result == 'no'

    def test_lt_one_arg(self):
        """lt with only 1 arg returns False (line 243)."""
        result = _extra_env.render('{{#if (lt a)}}yes{{else}}no{{/if}}', {'a': 5})
        assert result == 'no'

    def test_lte_one_arg(self):
        """lte with only 1 arg returns False (line 250)."""
        result = _extra_env.render('{{#if (lte a)}}yes{{else}}no{{/if}}', {'a': 5})
        assert result == 'no'

    def test_gt_incomparable_types(self):
        result = _extra_env.render('{{#if (gt a b)}}yes{{else}}no{{/if}}', {'a': 'hello', 'b': 5})
        assert result == 'no'

    def test_gte_incomparable_types(self):
        result = _extra_env.render('{{#if (gte a b)}}yes{{else}}no{{/if}}', {'a': 'hello', 'b': 5})
        assert result == 'no'

    def test_lt_incomparable_types(self):
        result = _extra_env.render('{{#if (lt a b)}}yes{{else}}no{{/if}}', {'a': 'hello', 'b': 5})
        assert result == 'no'

    def test_lte_incomparable_types(self):
        result = _extra_env.render('{{#if (lte a b)}}yes{{else}}no{{/if}}', {'a': 'hello', 'b': 5})
        assert result == 'no'


# --- Boolean helpers with no args: lines 257, 267, 277 ---


class TestBooleanHelpersNoArgs:
    def test_and_no_args(self):
        """and with no args returns False (line 257)."""
        result = _extra_env.render('{{#if (and)}}yes{{else}}no{{/if}}', {})
        assert result == 'no'

    def test_or_no_args(self):
        """or with no args returns False (line 267)."""
        result = _extra_env.render('{{#if (or)}}yes{{else}}no{{/if}}', {})
        assert result == 'no'

    def test_not_no_args(self):
        """not with no args returns True (line 277)."""
        result = _extra_env.render('{{#if (not)}}yes{{else}}no{{/if}}', {})
        assert result == 'yes'


# --- Default helper with < 2 args: line 284 ---


class TestDefaultEdgeCases:
    def test_default_one_arg(self):
        """default with 1 arg returns that arg (line 284)."""
        result = _extra_env.render('{{default val}}', {'val': 'hello'})
        assert result == 'hello'

    def test_default_no_args(self):
        """default with no args returns None -> '' (line 284)."""
        result = _extra_env.render('{{#if (default)}}yes{{else}}no{{/if}}', {})
        assert result == 'no'
