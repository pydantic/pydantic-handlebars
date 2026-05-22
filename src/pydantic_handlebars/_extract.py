"""Static dependency extraction for Handlebars templates.

Walks a parsed template AST and reports which top-level context keys the
template depends on, without rendering it. Useful for callers that need to
know which variables to provide before invoking a template — for example,
prompt-composition systems that sync a template's required inputs to a
database, or tooling that displays "this template uses fields X, Y, Z".
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic_handlebars._ast_nodes import (
    BlockStatement,
    Expression,
    MustacheStatement,
    PathExpression,
    Program,
    Statement,
    SubExpression,
)
from pydantic_handlebars._helpers import get_extra_helpers, get_standard_helpers
from pydantic_handlebars._parser import parse

# Built-in block helpers whose first positional argument names the new
# context — references inside the block body at depth 0 are against that
# new context, not the parent. Block helpers not in this set (custom user
# helpers, `if`, `unless`) leave the context unchanged for their body.
_CONTEXT_SHIFTING_HELPERS = frozenset({'each', 'with'})


@dataclass(slots=True)
class _ExtractScope:
    """Scope tracking for the extractor.

    Mirrors the shape the renderer maintains at runtime: each scope has a
    parent, a set of block parameters that locally shadow context names, and
    a flag indicating whether the scope shifted the context (`each` / `with`).
    """

    parent: _ExtractScope | None
    block_params: frozenset[str] = frozenset()
    is_opaque: bool = False
    """`True` when this scope sits inside `{{#each}}` / `{{#with}}`.

    References at `depth == 0` inside an opaque scope are against the
    shifted context (the iteration item or the new context), so they do not
    contribute to the *top-level* dependency set. Only references that walk
    back up to the root through `../` count.
    """


class _Extractor:
    """Walks an AST and collects top-level context references."""

    def __init__(self, known_helpers: set[str]) -> None:
        self._known_helpers = known_helpers
        self._deps: set[str] = set()

    def collect(self, program: Program) -> set[str]:
        """Walk *program* and return the set of top-level references found."""
        root = _ExtractScope(parent=None)
        self._walk_program(program, root)
        return self._deps

    # ------------------------------------------------------------------
    # Scope traversal
    # ------------------------------------------------------------------

    def _walk_program(self, program: Program, scope: _ExtractScope) -> None:
        for stmt in program.body:
            self._walk_statement(stmt, scope)

    def _walk_statement(self, stmt: Statement, scope: _ExtractScope) -> None:
        if isinstance(stmt, MustacheStatement):
            self._walk_mustache(stmt, scope)
        elif isinstance(stmt, BlockStatement):
            self._walk_block(stmt, scope)
        # ContentStatement, CommentStatement, RawBlock have no expression
        # references that would contribute to dependencies.

    def _walk_mustache(self, stmt: MustacheStatement, scope: _ExtractScope) -> None:
        # The mustache path itself: helper name or a context reference. The
        # parser only produces PathExpression or SubExpression here.
        if isinstance(stmt.path, SubExpression):
            self._walk_subexpression(stmt.path, scope)
        else:
            assert isinstance(stmt.path, PathExpression)
            self._record_path_or_helper(stmt.path, scope, has_args=bool(stmt.params or stmt.hash_pairs))

        # Positional and hash arguments are always values from the context
        # (or further subexpressions), never helper invocations themselves.
        for param in stmt.params:
            self._walk_expression(param, scope)
        for value in stmt.hash_pairs.values():
            self._walk_expression(value, scope)

    def _walk_block(self, stmt: BlockStatement, scope: _ExtractScope) -> None:
        # The parser only ever produces a PathExpression for a block's helper
        # name (see `_parse_block` in `_parser.py`). The `BlockStatement
        # .path` field is typed loosely as `Expression` but a subexpression
        # in that position is rejected at parse time, so we don't handle it
        # here.
        assert isinstance(stmt.path, PathExpression)
        name = stmt.path.original
        is_shifting = name in _CONTEXT_SHIFTING_HELPERS and name in self._known_helpers
        # The block helper *name* never counts as a dependency. Its
        # positional arguments do, but those are walked below.
        if name not in self._known_helpers:
            # User-provided block helper whose name is not registered:
            # treat it as a context reference so we don't silently drop
            # an unknown name. (Matches what the renderer would do — it
            # would try to look up the value on the context.)
            self._record_path(stmt.path, scope)

        for param in stmt.params:
            self._walk_expression(param, scope)
        for value in stmt.hash_pairs.values():
            self._walk_expression(value, scope)

        body_scope = _ExtractScope(
            parent=scope,
            block_params=frozenset(stmt.block_params),
            is_opaque=is_shifting,
        )
        self._walk_program(stmt.body, body_scope)
        if stmt.inverse is not None:
            # The inverse branch (`{{else}}`) renders against the *same*
            # context as the parent — context-shifting only applies to the
            # main body of `each` / `with`.
            inverse_scope = _ExtractScope(
                parent=scope,
                block_params=frozenset(stmt.block_params),
                is_opaque=False,
            )
            self._walk_program(stmt.inverse, inverse_scope)

    def _walk_subexpression(self, expr: SubExpression, scope: _ExtractScope) -> None:
        # The subexpression path is always a helper (parser-enforced).
        # Its arguments may be paths/literals/further subexpressions.
        for param in expr.params:
            self._walk_expression(param, scope)
        for value in expr.hash_pairs.values():
            self._walk_expression(value, scope)

    def _walk_expression(self, expr: Expression, scope: _ExtractScope) -> None:
        if isinstance(expr, PathExpression):
            self._record_path(expr, scope)
        elif isinstance(expr, SubExpression):
            self._walk_subexpression(expr, scope)
        # Literals (string/number/bool/null/undefined) contribute nothing.

    # ------------------------------------------------------------------
    # Reference recording
    # ------------------------------------------------------------------

    def _record_path_or_helper(self, path: PathExpression, scope: _ExtractScope, *, has_args: bool) -> None:
        """Record *path* as either a helper call (skip) or a context reference.

        A bare `{{name}}` is ambiguous at parse time — it could be either a
        helper with no arguments or a path lookup. The renderer resolves this
        by preferring the helper when one is registered AND the expression
        has arguments; otherwise it falls back to a path lookup. We follow
        the same rule.
        """
        if (
            not path.data
            and path.depth == 0
            and not path.is_this
            and len(path.parts) == 1
            and path.parts[0] in self._known_helpers
            and has_args
        ):
            # Helper invocation — the helper name itself is not a context dep.
            return
        self._record_path(path, scope)

    def _record_path(self, path: PathExpression, scope: _ExtractScope) -> None:
        # `@data` variables (`@index`, `@key`, `@root`, …) do not
        # name top-level context fields. The one exception is `@root.x`,
        # which explicitly reaches the root context — record `x`.
        if path.data:
            if path.parts and path.parts[0] == 'root' and len(path.parts) > 1:
                self._deps.add(path.parts[1])
            return

        if path.is_this or not path.parts:
            # `{{this}}` / `{{.}}` references the current context as a
            # whole, not a named field.
            return

        # Walk up the scope chain by `depth` to find which scope this
        # reference actually lands in. If we reach the root scope (parent is
        # None) and the scope was not opaque along the way, the reference is
        # a top-level dependency.
        target = scope
        for _ in range(path.depth):
            if target.parent is None:
                # `../` past the root resolves to the root in the renderer
                # (`get_parent_context` returns `None` past root). Treat
                # the reference as still landing on the root context.
                break
            target = target.parent

        first = path.parts[0]
        if first in target.block_params:
            # Locally bound by `as |name|` — not a context dep.
            return
        if target.is_opaque:
            # Reference is against a context that `each` / `with` shifted
            # to. Without knowing the inner shape we cannot map this back to
            # a top-level field name.
            return
        # The reference walked all the way back to a non-opaque scope: this
        # IS a top-level dep.
        self._deps.add(first)


def extract_dependencies(
    source: str,
    *,
    helpers: set[str] | None = None,
    include_extra_helpers: bool = False,
    open_delim: str = '{{',
    close_delim: str = '}}',
) -> set[str]:
    """Return the set of top-level context field names *source* depends on.

    Statically walks the template AST — no rendering or context is required.
    Useful for tooling that needs to know "what fields does this template
    expect" without actually executing it: dependency resolution, prompt
    composition systems, dataset generation, etc.

    Args:
        source: Handlebars template source.
        helpers: Names of additional helpers to recognise. Names registered
            as helpers are not treated as context references — for example,
            `{{format date}}` records `date` as a dependency but not
            `format`.
        include_extra_helpers: When `True`, also treat the non-spec helpers
            registered by `HandlebarsEnvironment(extra_helpers=True)`
            (`json`, `uppercase`, `eq`, …) as known helpers. Match this
            to the environment you intend to render with.
        open_delim: Open mustache delimiter. Defaults to `{{`. Pass the
            same delimiters you'd render the template with.
        close_delim: Close mustache delimiter. Defaults to `}}`.

    Returns:
        Set of top-level context field names referenced by the template.
        Empty if the template only contains literal content, `@data`
        variables, or references shadowed by block parameters.

    Raises:
        HandlebarsParseError: If the template cannot be parsed.

    Examples:
        ```python
        extract_dependencies('Hello {{user_name}}!') == {'user_name'}
        extract_dependencies('{{user.name}} <{{user.email}}>') == {'user'}
        extract_dependencies('{{#if beta}}new{{else}}{{tagline}}{{/if}}') == {'beta', 'tagline'}
        extract_dependencies('{{#each items}}{{name}}{{/each}}') == {'items'}
        extract_dependencies('{{#each items}}{{../top}}{{/each}}') == {'items', 'top'}
        ```
    """
    known = set(get_standard_helpers().keys())
    if include_extra_helpers:
        known.update(get_extra_helpers().keys())
    if helpers:
        known.update(helpers)

    program = parse(source, open_delim=open_delim, close_delim=close_delim)
    return _Extractor(known).collect(program)
