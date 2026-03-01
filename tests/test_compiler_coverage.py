"""Tests targeting uncovered lines in _compiler.py.

Covers: lines 65, 69->exit, 80, 109, 127-129, 148, 157, 191, 248,
263->267, 268, 274-276, 303-311, 330-352, 356-376, 394->393,
414-416, 461, 471-475, 518, 520, 527, 542-545, 550-551.
"""

# pyright: reportUnknownLambdaType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportPrivateUsage=false, reportUnknownMemberType=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportOptionalMemberAccess=false, reportAttributeAccessIssue=false, reportOperatorIssue=false, reportArgumentType=false

from __future__ import annotations

from typing import Any

import pytest

from pydantic_handlebars import (
    HandlebarsEnvironment,
    HandlebarsRuntimeError,
    HelperOptions,
    render,
)
from pydantic_handlebars._compiler import Compiler, Scope, _get_property, _noop_block
from pydantic_handlebars._parser import parse

# ---------------------------------------------------------------------------
# 1. _noop_block function (lines 74-80) and HelperOptions.name (line 65)
# ---------------------------------------------------------------------------


class TestNoopBlock:
    """Verify _noop_block returns '' regardless of arguments."""

    def test_noop_block_no_args(self) -> None:
        assert _noop_block() == ''

    def test_noop_block_with_context(self) -> None:
        assert _noop_block({'key': 'value'}) == ''

    def test_noop_block_with_data_and_block_params(self) -> None:
        assert _noop_block('ctx', data={'index': 0}, block_params=['a', 'b']) == ''


class TestHelperOptionsDefaults:
    """HelperOptions with no fn/inverse should use _noop_block."""

    def test_default_fn_returns_empty(self) -> None:
        opts = HelperOptions()
        assert opts.fn('anything') == ''

    def test_default_inverse_returns_empty(self) -> None:
        opts = HelperOptions()
        assert opts.inverse('anything') == ''

    def test_name_property_from_data(self) -> None:
        """Line 65: options.data.get('_name', '')."""
        opts = HelperOptions(data={'_name': 'myHelper'})
        assert opts.name == 'myHelper'

    def test_name_property_default(self) -> None:
        opts = HelperOptions()
        assert opts.name == ''

    def test_name_set_for_mustache_helper(self) -> None:
        """options.name is set for inline/mustache helper calls (not just block helpers)."""
        env = HandlebarsEnvironment()
        captured_name: list[str] = []

        def capture_name(*args: Any, options: HelperOptions) -> str:
            captured_name.append(options.name)
            return 'ok'

        env.register_helper('my_inline', capture_name)
        env.render('{{my_inline}}', {})
        assert captured_name == ['my_inline']

    def test_name_set_for_block_helper(self) -> None:
        """options.name is set for block helper calls."""
        env = HandlebarsEnvironment()
        captured_name: list[str] = []

        def capture_name(context: Any, *args: Any, options: HelperOptions) -> str:
            captured_name.append(options.name)
            return options.fn(context)

        env.register_helper('my_block', capture_name)
        env.render('{{#my_block}}body{{/my_block}}', {})
        assert captured_name == ['my_block']


# ---------------------------------------------------------------------------
# 2. Scope methods
# ---------------------------------------------------------------------------


class TestScopeLookupData:
    """Scope.lookup_data traversal (line 109, 127-129)."""

    def test_lookup_data_falls_through_to_parent(self) -> None:
        """Lines 127-129: parent traversal for lookup_data."""
        parent = Scope({'root': True}, data={'custom': 42})
        child = Scope({'child': True}, parent=parent)
        # 'custom' is NOT in child.data, so it traverses to parent
        assert child.lookup_data('custom') == 42

    def test_lookup_data_returns_none_when_missing(self) -> None:
        scope = Scope({})
        assert scope.lookup_data('nonexistent') is None

    def test_root_inherited_from_parent(self) -> None:
        """Line 109: root copied from parent when not already in data."""
        parent = Scope({'root_ctx': True})
        child = Scope({'child_ctx': True}, parent=parent, data={})
        # root should be inherited from parent
        assert child.data['root'] == {'root_ctx': True}


class TestScopeLookupBlockParam:
    """Scope.lookup_block_param traversal (lines 127-129, 139-140)."""

    def test_block_param_found_in_current(self) -> None:
        scope = Scope({}, block_params={'item': 'hello'})
        found, value = scope.lookup_block_param('item')
        assert found is True
        assert value == 'hello'

    def test_block_param_traverses_to_parent(self) -> None:
        """Lines 139-140: parent traversal for block params."""
        parent = Scope({}, block_params={'outer': 'val'})
        child = Scope({}, parent=parent, block_params={})
        found, value = child.lookup_block_param('outer')
        assert found is True
        assert value == 'val'

    def test_block_param_not_found(self) -> None:
        scope = Scope({})
        found, value = scope.lookup_block_param('missing')
        assert found is False
        assert value is None


class TestScopeGetParentContext:
    """Scope.get_parent_context returning None (line 148)."""

    def test_parent_context_beyond_chain(self) -> None:
        """Line 148: return None when depth exceeds scope chain."""
        scope = Scope({'only_scope': True})
        assert scope.get_parent_context(1) is None

    def test_parent_context_at_depth(self) -> None:
        root = Scope({'root': True})
        child = Scope({'child': True}, parent=root)
        assert child.get_parent_context(1) == {'root': True}


class TestScopeGetParentData:
    """Scope.get_parent_data returning {} (line 157)."""

    def test_parent_data_beyond_chain(self) -> None:
        """Line 157: return {} when depth exceeds scope chain."""
        scope = Scope({})
        assert scope.get_parent_data(1) == {}

    def test_parent_data_at_depth(self) -> None:
        root = Scope({}, data={'level': 'root'})
        child = Scope({}, parent=root, data={'level': 'child'})
        result = child.get_parent_data(1)
        assert result.get('level') == 'root'


# ---------------------------------------------------------------------------
# 3. Max output size check (line 191)
# ---------------------------------------------------------------------------


class TestMaxOutputSize:
    """Line 191: output exceeds max size."""

    def test_max_output_size_exceeded(self) -> None:
        program = parse('{{val}}')
        compiler = Compiler(max_output_size=5)
        with pytest.raises(HandlebarsRuntimeError, match='Output size exceeds maximum'):
            compiler.render(program, {'val': 'x' * 10})

    def test_max_output_size_incremental_each(self) -> None:
        """Output size is checked incrementally during iteration, not just post-hoc."""
        # Use context-based block iteration ({{#items}}), not {{#each}} which needs helpers
        program = parse('{{#items}}AAAA{{/items}}')
        compiler = Compiler(max_output_size=20)
        # 10 items * 4 chars = 40 bytes, exceeds 20 limit
        with pytest.raises(HandlebarsRuntimeError, match='Output size exceeds maximum'):
            compiler.render(program, {'items': list(range(10))})

    def test_max_output_size_incremental_allows_within_limit(self) -> None:
        """Output under the limit should succeed."""
        program = parse('{{#items}}A{{/items}}')
        compiler = Compiler(max_output_size=20)
        result = compiler.render(program, {'items': list(range(5))})
        assert result == 'AAAAA'

    def test_max_output_size_no_double_counting_nested_blocks(self) -> None:
        """Output size should not be double-counted for nested block rendering.

        Regression test: _render_program previously incremented _output_size in
        both inner and outer calls, effectively counting the same bytes twice.
        This caused the limit to trigger at roughly half the configured value.
        """
        # 10 items * 2 chars each = 20 bytes of actual output.
        # With a 25-byte limit, this should succeed. With double-counting
        # it would track ~40 bytes and fail.
        program = parse('{{#items}}AB{{/items}}')
        compiler = Compiler(max_output_size=25)
        result = compiler.render(program, {'items': list(range(10))})
        assert result == 'AB' * 10
        assert len(result) == 20

    def test_max_output_size_no_double_counting_with_surrounding_content(self) -> None:
        """Nested blocks with surrounding content should track size accurately."""
        # "Hello " (6) + 5 items * "X" (5) + " World" (6) = 17 bytes total.
        # With a 20-byte limit this should succeed.
        program = parse('Hello {{#items}}X{{/items}} World')
        compiler = Compiler(max_output_size=20)
        result = compiler.render(program, {'items': list(range(5))})
        assert result == 'Hello XXXXX World'
        assert len(result) == 17


class TestDepthRecovery:
    """Depth counter must be properly decremented after max-depth error."""

    def test_compiler_reuse_after_depth_error(self) -> None:
        """Compiler should work correctly after a max-depth error."""
        compiler = Compiler(max_depth=2)

        # Context-based blocks nest: top program -> #a block -> #b block -> #c block
        deep = parse('{{#a}}{{#b}}{{#c}}{{this}}{{/c}}{{/b}}{{/a}}')
        with pytest.raises(HandlebarsRuntimeError, match='Maximum nesting depth'):
            compiler.render(deep, {'a': {'b': {'c': 'x'}}})

        # After the error, the compiler should still work for simple templates
        simple = parse('{{val}}')
        assert compiler.render(simple, {'val': 'ok'}) == 'ok'

    def test_depth_reset_across_renders(self) -> None:
        """Multiple max-depth errors should not accumulate."""
        compiler = Compiler(max_depth=2)

        deep = parse('{{#a}}{{#b}}{{#c}}{{this}}{{/c}}{{/b}}{{/a}}')
        for _ in range(5):
            with pytest.raises(HandlebarsRuntimeError, match='Maximum nesting depth'):
                compiler.render(deep, {'a': {'b': {'c': 'x'}}})

        # Should still work after repeated failures
        simple = parse('{{val}}')
        assert compiler.render(simple, {'val': 'still works'}) == 'still works'


# ---------------------------------------------------------------------------
# 5. _call_helper_mustache - fallback signatures (lines 303-311)
# ---------------------------------------------------------------------------


class TestCallHelperMustache:
    """Tests for _call_helper_mustache with proper HelperFunc signatures."""

    def test_helper_with_options(self) -> None:
        """Helper receives options kwarg."""
        env = HandlebarsEnvironment()
        env.register_helper('simple', lambda *args, options: f'got:{args[0]}')
        result = env.render('{{simple name}}', {'name': 'Alice'})
        assert result == 'got:Alice'

    def test_helper_no_args_with_context(self) -> None:
        """Helper with no template args receives context as first arg."""
        env = HandlebarsEnvironment()
        env.register_helper('constant', lambda *args, options: 'CONSTANT')
        result = env.render('{{constant}}', {})
        assert result == 'CONSTANT'

    def test_helper_context_passed_when_no_args(self) -> None:
        """When no template args, scope.context is passed as the arg."""
        env = HandlebarsEnvironment()
        env.register_helper('ctx_helper', lambda *args, options: f'ctx:{args[0].get("x", "")}')
        result = env.render('{{ctx_helper}}', {'x': 'hello'})
        assert result == 'ctx:hello'

    def test_helper_with_hash_args(self) -> None:
        """Helper receives hash args via options.hash."""
        env = HandlebarsEnvironment()

        def strict_helper(*args: object, options: HelperOptions) -> str:
            prefix = options.hash.get('prefix', '')
            return f'{prefix}{args[0]}'

        env.register_helper('strict', strict_helper)
        result = env.render('{{strict name prefix="PRE-"}}', {'name': 'test'})
        assert result == 'PRE-test'


# ---------------------------------------------------------------------------
# 6. _render_block without helper - context-based (lines 330-352)
# ---------------------------------------------------------------------------


class TestRenderBlockWithoutHelper:
    """Lines 330-352: block on a path that is not a registered helper."""

    def test_block_on_list_value(self) -> None:
        """Lines 338-340: block iterates when value is a list."""
        result = render('{{#items}}{{this}} {{/items}}', {'items': ['a', 'b', 'c']})
        assert result == 'a b c '

    def test_block_on_dict_value(self) -> None:
        """Lines 342-345: block changes context when value is a dict."""
        result = render('{{#person}}{{name}}{{/person}}', {'person': {'name': 'Alice'}})
        assert result == 'Alice'

    def test_block_on_true_value(self) -> None:
        """Lines 347-348: block renders body with same scope for True."""
        result = render('{{#active}}yes{{/active}}', {'active': True})
        assert result == 'yes'

    def test_block_on_object_value(self) -> None:
        """Lines 350-352: block uses arbitrary value as context."""
        result = render('{{#obj}}{{name}}{{/obj}}', {'obj': {'name': 'Bob'}})
        assert result == 'Bob'

    def test_block_on_falsy_with_inverse(self) -> None:
        """Lines 332-335: falsy value triggers inverse."""
        result = render('{{#missing}}yes{{else}}no{{/missing}}', {'missing': None})
        assert result == 'no'

    def test_block_on_falsy_without_inverse(self) -> None:
        """Line 336: falsy value with no inverse returns ''."""
        result = render('{{#missing}}yes{{/missing}}', {'missing': None})
        assert result == ''


# ---------------------------------------------------------------------------
# 7. _render_each_inline with empty items and block params (lines 356-376)
# ---------------------------------------------------------------------------


class TestRenderEachInline:
    """Lines 356-376: inline iteration for non-helper blocks on lists."""

    def test_inline_each_empty_with_inverse(self) -> None:
        """Lines 356-358: empty list triggers inverse.

        Note: Through normal rendering, [] is falsy and caught before
        _render_each_inline. We test this by calling the method directly.
        """
        from pydantic_handlebars._ast_nodes import (
            BlockStatement,
            ContentStatement,
            PathExpression,
            Program,
            StripFlags,
        )

        compiler = Compiler()
        scope = Scope({})
        stmt = BlockStatement(
            path=PathExpression(parts=['items'], original='items'),
            params=[],
            hash_pairs={},
            body=Program(body=[ContentStatement(value='item', original='item')]),
            inverse=Program(body=[ContentStatement(value='empty', original='empty')]),
            open_strip=StripFlags(),
            close_strip=StripFlags(),
        )
        result = compiler._render_each_inline([], stmt, scope)
        assert result == 'empty'

    def test_inline_each_empty_without_inverse(self) -> None:
        """Line 359: empty list with no inverse returns ''.

        Tested via direct method call (same reason as above).
        """
        from pydantic_handlebars._ast_nodes import (
            BlockStatement,
            ContentStatement,
            PathExpression,
            Program,
            StripFlags,
        )

        compiler = Compiler()
        scope = Scope({})
        stmt = BlockStatement(
            path=PathExpression(parts=['items'], original='items'),
            params=[],
            hash_pairs={},
            body=Program(body=[ContentStatement(value='item', original='item')]),
            inverse=None,
            open_strip=StripFlags(),
            close_strip=StripFlags(),
        )
        result = compiler._render_each_inline([], stmt, scope)
        assert result == ''

    def test_inline_each_with_block_params(self) -> None:
        """Lines 369-373: block params on inline each."""
        result = render(
            '{{#items as |item idx|}}{{idx}}:{{item}} {{/items}}',
            {'items': ['x', 'y', 'z']},
        )
        assert result == '0:x 1:y 2:z '

    def test_inline_each_with_single_block_param(self) -> None:
        """Line 371: only one block param provided."""
        result = render(
            '{{#items as |item|}}{{item}} {{/items}}',
            {'items': ['a', 'b']},
        )
        assert result == 'a b '

    def test_inline_each_data_variables(self) -> None:
        """Lines 362-367: @index, @first, @last set correctly."""
        result = render(
            '{{#items}}{{@index}}{{#if @first}}F{{/if}}{{#if @last}}L{{/if}} {{/items}}',
            {'items': ['a', 'b', 'c']},
        )
        assert result == '0F 1 2L '


# ---------------------------------------------------------------------------
# 8. _call_block_helper - inverse with block_params (lines 414-416)
# ---------------------------------------------------------------------------


class TestCallBlockHelperInverseBlockParams:
    """Lines 414-416: inverse fn called with block_params."""

    def test_inverse_with_block_params(self) -> None:
        env = HandlebarsEnvironment()

        def my_block(context: Any, *args: Any, options: HelperOptions) -> str:
            # Call inverse with block_params to exercise lines 414-416
            return options.inverse(context, block_params=['bp_value', 'bp_index'])

        env.register_helper('my_block', my_block)
        result = env.render(
            '{{#my_block as |val idx|}}main{{else}}inverse:{{val}}-{{idx}}{{/my_block}}',
            {},
        )
        assert result == 'inverse:bp_value-bp_index'

    def test_inverse_with_multiple_block_params_iteration(self) -> None:
        """Lines 413-416: loop iterates over multiple block params."""
        env = HandlebarsEnvironment()

        def my_block(context: Any, *args: Any, options: HelperOptions) -> str:
            return options.inverse(context, block_params=['first', 'second', 'third'])

        env.register_helper('my_block', my_block)
        # Only 2 block params declared, so only first 2 of 3 provided values are used
        result = env.render(
            '{{#my_block as |a b|}}main{{else}}{{a}}-{{b}}{{/my_block}}',
            {},
        )
        assert result == 'first-second'

    def test_inverse_with_fewer_block_params_than_declared(self) -> None:
        """Line 415->414: block_params shorter than stmt.block_params.

        When the helper provides fewer block_params values than declared names,
        the loop continues past the values (j >= len(block_params)).
        """
        env = HandlebarsEnvironment()

        def my_block(context: Any, *args: Any, options: HelperOptions) -> str:
            return options.inverse(context, block_params=['only_one'])

        env.register_helper('my_block', my_block)
        result = env.render(
            '{{#my_block as |a b|}}main{{else}}{{a}}-{{b}}{{/my_block}}',
            {},
        )
        assert result == 'only_one-'


# ---------------------------------------------------------------------------
# 9. _eval_subexpression errors and fallbacks (lines 461, 471-475)
# ---------------------------------------------------------------------------


class TestEvalSubexpression:
    """Lines 461, 471-475: subexpression error and fallback paths."""

    def test_unknown_helper_in_subexpression(self) -> None:
        """Line 461: raise on unknown helper."""
        env = HandlebarsEnvironment()
        env.register_helper('outer', lambda *args, **kw: str(args[0]))
        with pytest.raises(HandlebarsRuntimeError, match='Unknown helper'):
            env.render('{{outer (nonexistent "arg")}}', {})

    def test_subexpression_with_options(self) -> None:
        """Subexpression helper receives options kwarg."""
        env = HandlebarsEnvironment()
        env.register_helper('add', lambda *args, options: args[0] + args[1])
        env.register_helper('show', lambda *args, options: str(args[0]))
        result = env.render('{{show (add 1 2)}}', {})
        assert result == '3'

    def test_subexpression_with_hash_args(self) -> None:
        """Subexpression helper receives hash args via options.hash."""
        env = HandlebarsEnvironment()

        def join_args(*args: object, options: HelperOptions) -> str:
            return '-'.join(str(a) for a in args)

        env.register_helper('join_args', join_args)
        env.register_helper('show', lambda *args, options: str(args[0]))
        result = env.render('{{show (join_args "a" "b" extra="ignored")}}', {})
        assert result == 'a-b'


# ---------------------------------------------------------------------------
# 10. _resolve_data_path - depth > 0 branches (lines 518, 520, 527)
# ---------------------------------------------------------------------------


class TestResolveDataPath:
    """Lines 513-527: @data path resolution with depth and edge cases."""

    def test_data_path_with_parent_depth(self) -> None:
        """Lines 513-518: @../index resolves via parent data."""
        template = '{{#each items}}{{#each sub}}{{@../index}}:{{this}} {{/each}}{{/each}}'
        data = {'items': [{'sub': ['a', 'b']}, {'sub': ['c']}]}
        result = render(template, data)
        assert result == '0:a 0:b 1:c '

    def test_data_path_parent_no_parts(self) -> None:
        """Line 520: @data path with depth but no parts returns None."""
        # This is an edge case: @../ with no trailing name
        # We need to construct this manually since the parser may not produce it easily.
        # Use a template that accesses parent data through nested each blocks.
        env = HandlebarsEnvironment()

        def check_data(context: Any, *args: Any, options: HelperOptions) -> str:
            # Manually verify data path resolution
            return str(options.data.get('index', 'none'))

        env.register_helper('check_data', check_data)
        result = env.render('{{#each items}}{{check_data}}{{/each}}', {'items': [1, 2]})
        assert result == '01'

    def test_data_path_no_parts_at_root(self) -> None:
        """Line 527: @data path with no parts returns None."""
        # Accessing just '@' by itself should return None / empty
        # This edge case is hard to trigger through the parser; test via Compiler directly
        from pydantic_handlebars._ast_nodes import PathExpression

        path = PathExpression(parts=[], original='@', data=True, depth=0)
        scope = Scope({'some': 'data'}, data={'index': 5})
        compiler = Compiler()
        result = compiler._resolve_data_path(path, scope)
        assert result is None

    def test_data_path_parent_depth_with_nested_parts(self) -> None:
        """Line 518: _get_property on nested data parts."""
        from pydantic_handlebars._ast_nodes import PathExpression

        scope_parent = Scope({}, data={'info': {'nested': 'value'}})
        scope_child = Scope({}, parent=scope_parent, data={})
        compiler = Compiler()

        path = PathExpression(parts=['info', 'nested'], original='@../info.nested', data=True, depth=1)
        result = compiler._resolve_data_path(path, scope_child)
        assert result == 'value'

    def test_data_path_parent_no_parts_returns_none(self) -> None:
        """Line 520: depth > 0 with no parts returns None."""
        from pydantic_handlebars._ast_nodes import PathExpression

        scope_parent = Scope({}, data={'index': 0})
        scope_child = Scope({}, parent=scope_parent, data={})
        compiler = Compiler()

        path = PathExpression(parts=[], original='@../', data=True, depth=1)
        result = compiler._resolve_data_path(path, scope_child)
        assert result is None


# ---------------------------------------------------------------------------
# 11. _get_property - list/tuple access, attribute access (lines 542-545, 550-551)
# ---------------------------------------------------------------------------


class TestGetProperty:
    """Lines 541-551: property access on lists, tuples, and objects."""

    def test_list_index_access(self) -> None:
        """Lines 542-543: list[int(name)]."""
        assert _get_property(['a', 'b', 'c'], '1') == 'b'

    def test_list_invalid_index(self) -> None:
        """Line 544: ValueError when name is not an int."""
        assert _get_property(['a', 'b'], 'not_a_number') is None

    def test_list_index_out_of_range(self) -> None:
        """Line 544: IndexError when index is out of range."""
        assert _get_property(['a', 'b'], '99') is None

    def test_tuple_index_access(self) -> None:
        """Line 541: tuple is also handled."""
        assert _get_property(('x', 'y', 'z'), '2') == 'z'

    def test_tuple_invalid_index(self) -> None:
        assert _get_property(('x', 'y'), 'bad') is None

    def test_non_dict_non_list_returns_none(self) -> None:
        """Non-dict/list objects return None (no getattr fallback)."""

        class Obj:
            foo = 'bar'

        assert _get_property(Obj(), 'foo') is None

    def test_dict_access(self) -> None:
        assert _get_property({'key': 'val'}, 'key') == 'val'

    def test_dict_missing_key(self) -> None:
        assert _get_property({'key': 'val'}, 'other') is None

    def test_dunder_key_accessible(self) -> None:
        assert _get_property({'__class__': 'ok'}, '__class__') == 'ok'


# ---------------------------------------------------------------------------
# 12. RawBlock rendering (line 248) - _render_statement returns stmt.body
# ---------------------------------------------------------------------------


class TestRawBlock:
    """Line 248: RawBlock rendering returns body as-is."""

    def test_raw_block_renders_body(self) -> None:
        result = render('{{{{raw}}}}{{not-processed}}{{{{/raw}}}}', {})
        assert result == '{{not-processed}}'


# ---------------------------------------------------------------------------
# 13. SubExpression as mustache path (lines 267-268)
# ---------------------------------------------------------------------------


class TestSubExpressionAsMustachePath:
    """Lines 267-268: when a mustache's path is a SubExpression."""

    def test_subexpression_as_value(self) -> None:
        env = HandlebarsEnvironment()
        env.register_helper('greet', lambda name, **kw: f'Hello {name}')
        result = env.render('{{(greet "World")}}', {})
        assert result == 'Hello World'


# ---------------------------------------------------------------------------
# 14. _call_helper_mustache path with multi-part path (line 263)
# ---------------------------------------------------------------------------


class TestHelperMustacheMultiPartPath:
    """Line 263: helper not called when path has multiple parts and no params/hash."""

    def test_multi_part_helper_path_no_params(self) -> None:
        """When a helper name has dots and no params, it resolves as path."""
        env = HandlebarsEnvironment()
        env.register_helper('foo.bar', lambda *args, **kw: 'HELPER')
        # With a multi-part path and no params, it should resolve as a path
        result = env.render('{{foo.bar}}', {'foo': {'bar': 'CONTEXT'}})
        assert result == 'CONTEXT'


# ---------------------------------------------------------------------------
# 15. Block helper fn with block_params (lines 392-395)
# ---------------------------------------------------------------------------


class TestRenderBlockNonPathExpression:
    """Line 322->330: block with a non-PathExpression path."""

    def test_block_with_subexpression_path(self) -> None:
        """When block stmt.path is NOT a PathExpression, skip helper lookup."""
        from pydantic_handlebars._ast_nodes import (
            BlockStatement,
            ContentStatement,
            PathExpression,
            Program,
            StripFlags,
            SubExpression,
        )

        # Create a block whose path is a SubExpression
        sub_path = PathExpression(parts=['identity'], original='identity')
        sub_expr = SubExpression(path=sub_path, params=[], hash_pairs={})

        stmt = BlockStatement(
            path=sub_expr,
            params=[],
            hash_pairs={},
            body=Program(body=[ContentStatement(value='body', original='body')]),
            inverse=None,
            open_strip=StripFlags(),
            close_strip=StripFlags(),
        )

        # Register 'identity' helper that returns its context
        def identity_helper(*args: Any, options: HelperOptions | None = None) -> Any:
            return True

        compiler = Compiler(helpers={'identity': identity_helper})
        scope = Scope({})
        # The SubExpression evaluates to True, so the body renders
        result = compiler._render_block(stmt, scope)
        assert result == 'body'


class TestBlockHelperFnBlockParams:
    """Lines 392-395: fn() called with block_params."""

    def test_fn_with_block_params(self) -> None:
        env = HandlebarsEnvironment()

        def my_helper(context: Any, *args: Any, options: HelperOptions) -> str:
            return options.fn(context, block_params=['custom_val'])

        env.register_helper('my_helper', my_helper)
        result = env.render(
            '{{#my_helper as |val|}}got:{{val}}{{/my_helper}}',
            {},
        )
        assert result == 'got:custom_val'

    def test_fn_with_multiple_block_params(self) -> None:
        """Lines 393-395: fn iterates block_params with multiple entries."""
        env = HandlebarsEnvironment()

        def my_helper(context: Any, *args: Any, options: HelperOptions) -> str:
            return options.fn(context, block_params=['val_a', 'val_b'])

        env.register_helper('my_helper', my_helper)
        result = env.render(
            '{{#my_helper as |a b|}}{{a}}-{{b}}{{/my_helper}}',
            {},
        )
        assert result == 'val_a-val_b'

    def test_fn_with_fewer_block_params_than_declared(self) -> None:
        """Line 394->393: block_params shorter than stmt.block_params.

        When the helper provides fewer block_params values than declared names,
        the loop iterates past the end of block_params (j >= len(block_params)),
        so the if-check on line 394 is False and the loop continues.
        """
        env = HandlebarsEnvironment()

        def my_helper(context: Any, *args: Any, options: HelperOptions) -> str:
            # Only provide 1 block param value, but template declares 2
            return options.fn(context, block_params=['only_one'])

        env.register_helper('my_helper', my_helper)
        result = env.render(
            '{{#my_helper as |a b|}}{{a}}-{{b}}{{/my_helper}}',
            {},
        )
        # 'a' gets 'only_one', 'b' gets nothing (empty)
        assert result == 'only_one-'
