"""JSON Schema compatibility checker for Handlebars templates.

Statically walks template ASTs and verifies field references against a JSON schema.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, TypeAlias, cast

from pydantic_handlebars._ast_nodes import (
    BlockStatement,
    Expression,
    MustacheStatement,
    PathExpression,
    Program,
    SubExpression,
)
from pydantic_handlebars._exceptions import TemplateSchemaError
from pydantic_handlebars._helpers import get_standard_helpers
from pydantic_handlebars._parser import parse

_JsonSchema = dict[str, Any]


IssueSeverity: TypeAlias = Literal['error', 'warning', 'ignore']


@dataclass(slots=True)
class TemplateIssue:
    """A single compatibility issue found during template checking.

    Attributes:
        severity: The severity level of the issue.
        message: A human-readable description of the issue.
        field_path: The dotted path to the field that caused the issue.
        template_index: The index of the template that contains the issue.
    """

    severity: IssueSeverity
    message: str
    field_path: str
    template_index: int


@dataclass(slots=True)
class CompatibilityResult:
    """Result of checking template compatibility with a JSON schema.

    Attributes:
        issues: List of all issues found during checking.
    """

    issues: list[TemplateIssue] = field(default_factory=list)  # pyright: ignore[reportUnknownVariableType]

    @property
    def is_compatible(self) -> bool:
        """Whether the templates are compatible (no ERROR-level issues)."""
        return not any(issue.severity == 'error' for issue in self.issues)


@dataclass(slots=True)
class _SchemaScope:
    """Mirrors Scope from _compiler.py but for schema traversal."""

    schema: _JsonSchema
    parent: _SchemaScope | None
    block_params: set[str]
    root_schema: _JsonSchema
    is_opaque: bool = False

    def child(
        self,
        schema: _JsonSchema,
        *,
        block_params: set[str] | None = None,
        is_opaque: bool = False,
    ) -> _SchemaScope:
        """Create a child scope."""
        return _SchemaScope(
            schema=schema,
            parent=self,
            block_params=block_params or set(),
            root_schema=self.root_schema,
            is_opaque=is_opaque,
        )

    def get_parent(self, depth: int) -> _SchemaScope:
        """Walk up the scope chain to get a parent scope."""
        scope: _SchemaScope = self
        for _ in range(depth):
            if scope.parent is None:
                return scope
            scope = scope.parent
        return scope


class _SchemaChecker:
    """Recursive walker that checks template ASTs against a JSON schema."""

    def __init__(
        self,
        root_schema: _JsonSchema,
        optional_field_severity: IssueSeverity,
        helpers: set[str],
    ) -> None:
        self._root_schema = root_schema
        self._optional_field_severity: IssueSeverity = optional_field_severity
        self._defs: dict[str, _JsonSchema] = {
            **root_schema.get('$defs', {}),
            **root_schema.get('definitions', {}),
        }
        default_helper_names = set(get_standard_helpers().keys())
        self._known_helpers = default_helper_names | helpers
        self._issues: list[TemplateIssue] = []
        self._template_index = 0
        self._resolving_refs: set[str] = set()

    def check(self, programs: list[Program]) -> list[TemplateIssue]:
        """Check all programs against the schema."""
        for i, program in enumerate(programs):
            self._template_index = i
            scope = _SchemaScope(
                schema=self._root_schema,
                parent=None,
                block_params=set(),
                root_schema=self._root_schema,
            )
            self._check_program(program, scope)
        return self._issues

    def _add_issue(self, severity: IssueSeverity, message: str, field_path: str) -> None:
        self._issues.append(
            TemplateIssue(
                severity=severity,
                message=message,
                field_path=field_path,
                template_index=self._template_index,
            )
        )

    def _check_program(self, program: Program, scope: _SchemaScope) -> None:
        for stmt in program.body:
            self._check_statement(stmt, scope)

    def _check_statement(self, stmt: MustacheStatement | BlockStatement | Any, scope: _SchemaScope) -> None:
        if isinstance(stmt, MustacheStatement):
            self._check_mustache(stmt, scope)
        elif isinstance(stmt, BlockStatement):
            self._check_block(stmt, scope)
        # ContentStatement, CommentStatement, RawBlock are skipped

    def _check_mustache(self, stmt: MustacheStatement, scope: _SchemaScope) -> None:
        """Check a mustache expression."""
        if isinstance(stmt.path, SubExpression):
            self._check_subexpression(stmt.path, scope)
            return

        if not isinstance(stmt.path, PathExpression):
            return  # Literal values (true, null, 42, etc.) don't reference fields

        path = stmt.path

        # @data variable
        if path.data:
            self._check_data_path(path, scope)
            return

        # Check if this is a helper call
        if path.depth == 0 and not path.is_this:
            helper_name = path.original
            if helper_name in self._known_helpers:
                if stmt.params or stmt.hash_pairs or len(path.parts) == 1:  # pragma: no branch
                    # Check for default helper pattern
                    if helper_name == 'default':
                        self._check_default_helper(stmt, scope)
                        return
                    # Validate params and hash arg values against schema
                    self._check_params(stmt.params, scope)
                    self._check_params(list(stmt.hash_pairs.values()), scope)
                    return

        self._check_path(path, scope)

    def _check_subexpression(self, expr: SubExpression, scope: _SchemaScope) -> None:
        """Check a subexpression's params and hash arg values."""
        self._check_params(expr.params, scope)
        self._check_params(list(expr.hash_pairs.values()), scope)

    def _check_params(self, params: list[Expression], scope: _SchemaScope) -> None:
        """Validate parameter expressions against the schema."""
        for param in params:
            if isinstance(param, PathExpression):
                if param.data:
                    self._check_data_path(param, scope)
                else:
                    self._check_path(param, scope)
            elif isinstance(param, SubExpression):
                self._check_subexpression(param, scope)

    def _check_block(self, stmt: BlockStatement, scope: _SchemaScope) -> None:
        """Check a block statement."""
        if not isinstance(stmt.path, PathExpression):  # pragma: no cover
            return  # Exotic chained-else with non-path expression

        path = stmt.path
        helper_name = path.original

        # Built-in block helpers
        if helper_name == 'if' or helper_name == 'unless':
            self._check_if_unless(stmt, scope)
            return

        if helper_name == 'each':
            self._check_each(stmt, scope)
            return

        if helper_name == 'with':
            self._check_with(stmt, scope)
            return

        # Registered/custom helpers
        if helper_name in self._known_helpers:
            # Validate params and hash arg values
            self._check_params(stmt.params, scope)
            self._check_params(list(stmt.hash_pairs.values()), scope)
            # Body is opaque — we don't know what context the helper provides
            opaque_scope = scope.child({}, is_opaque=True)
            self._check_program(stmt.body, opaque_scope)
            if stmt.inverse is not None:
                self._check_program(stmt.inverse, opaque_scope)
            return

        # Context-based block: {{#person}}...{{/person}}
        self._check_context_block(stmt, path, scope)

    def _check_if_unless(self, stmt: BlockStatement, scope: _SchemaScope) -> None:
        """Check #if / #unless blocks — condition is validated, body stays same scope."""
        # Validate the condition
        if stmt.params:
            self._check_params(stmt.params, scope)
        elif isinstance(stmt.path, PathExpression):  # pragma: no cover
            pass  # No params — condition is the current context, not a named field

        # Body and inverse stay in the same scope
        self._check_program(stmt.body, scope)
        if stmt.inverse is not None:
            self._check_inverse(stmt.inverse, scope)

    def _check_inverse(self, inverse: Program, scope: _SchemaScope) -> None:
        """Check an inverse program, handling chained else-if blocks."""
        for stmt in inverse.body:
            if isinstance(stmt, BlockStatement) and stmt.chained:
                self._check_block(stmt, scope)
            else:
                self._check_statement(stmt, scope)

    def _check_each(self, stmt: BlockStatement, scope: _SchemaScope) -> None:
        """Check #each blocks — resolve iterated schema."""
        if not stmt.params:
            # {{#each}} without params — iterate current context
            item_schema = self._get_each_item_schema(scope.schema)
            bp = self._get_block_param_names(stmt)
            is_opaque = bool(item_schema.get('_opaque', False))
            clean_schema: _JsonSchema = {k: v for k, v in item_schema.items() if k != '_opaque'}
            child = scope.child(clean_schema, block_params=bp, is_opaque=is_opaque)
            self._check_program(stmt.body, child)
            if stmt.inverse is not None:
                self._check_program(stmt.inverse, scope)
            return

        # {{#each items}} — resolve the path
        param = stmt.params[0]
        if isinstance(param, PathExpression):
            if param.data:
                self._check_data_path(param, scope)
                bp = self._get_block_param_names(stmt)
                child = scope.child({}, block_params=bp, is_opaque=True)
                self._check_program(stmt.body, child)
                if stmt.inverse is not None:
                    self._check_program(stmt.inverse, scope)
                return

            resolved = self._resolve_path_to_schema(param, scope)
            if resolved is None:
                # Path didn't resolve — already reported
                bp = self._get_block_param_names(stmt)
                child = scope.child({}, block_params=bp, is_opaque=True)
                self._check_program(stmt.body, child)
                if stmt.inverse is not None:
                    self._check_program(stmt.inverse, scope)
                return

            item_schema = self._get_each_item_schema(resolved)
            bp = self._get_block_param_names(stmt)
            is_opaque = bool(item_schema.get('_opaque', False))
            clean_schema = {k: v for k, v in item_schema.items() if k != '_opaque'}
            child = scope.child(clean_schema, block_params=bp, is_opaque=is_opaque)
            self._check_program(stmt.body, child)
            if stmt.inverse is not None:
                self._check_program(stmt.inverse, scope)
        else:
            # Literal or subexpression — can't check statically
            bp = self._get_block_param_names(stmt)
            child = scope.child({}, block_params=bp, is_opaque=True)
            self._check_program(stmt.body, child)
            if stmt.inverse is not None:
                self._check_program(stmt.inverse, scope)

    def _get_each_item_schema(self, schema: _JsonSchema) -> _JsonSchema:
        """Get the item schema for an #each iteration."""
        resolved = self._resolve_ref(schema)

        # Handle union types
        resolved = self._unwrap_nullable(resolved)

        schema_type = resolved.get('type')

        if schema_type == 'array':
            items = resolved.get('items', {})
            if isinstance(items, dict):
                return self._resolve_ref(cast('_JsonSchema', items))
            return {}

        if schema_type == 'object':
            # Iterating over object keys — use additionalProperties
            add_props = resolved.get('additionalProperties')
            if isinstance(add_props, dict):
                return self._resolve_ref(cast('_JsonSchema', add_props))
            return {'_opaque': True}

        # Unknown type — opaque
        return {'_opaque': True}

    def _check_with(self, stmt: BlockStatement, scope: _SchemaScope) -> None:
        """Check #with blocks — descend into referenced field's schema."""
        if not stmt.params:
            self._check_program(stmt.body, scope)
            if stmt.inverse is not None:
                self._check_program(stmt.inverse, scope)
            return

        param = stmt.params[0]
        if isinstance(param, PathExpression):
            if param.data:
                self._check_data_path(param, scope)
                bp = self._get_block_param_names(stmt)
                child = scope.child({}, block_params=bp, is_opaque=True)
                self._check_program(stmt.body, child)
                if stmt.inverse is not None:
                    self._check_program(stmt.inverse, scope)
                return

            resolved = self._resolve_path_to_schema(param, scope)
            if resolved is None:
                bp = self._get_block_param_names(stmt)
                child = scope.child({}, block_params=bp, is_opaque=True)
                self._check_program(stmt.body, child)
                if stmt.inverse is not None:
                    self._check_program(stmt.inverse, scope)
                return

            bp = self._get_block_param_names(stmt)
            child = scope.child(resolved, block_params=bp)
            self._check_program(stmt.body, child)
            if stmt.inverse is not None:
                self._check_program(stmt.inverse, scope)
        else:
            bp = self._get_block_param_names(stmt)
            child = scope.child({}, block_params=bp, is_opaque=True)
            self._check_program(stmt.body, child)
            if stmt.inverse is not None:
                self._check_program(stmt.inverse, scope)

    def _check_context_block(self, stmt: BlockStatement, path: PathExpression, scope: _SchemaScope) -> None:
        """Check a context-based block like {{#person}}...{{/person}}."""
        resolved = self._resolve_path_to_schema(path, scope)
        if resolved is None:
            # Path didn't resolve — already reported, check body as opaque
            child = scope.child({}, is_opaque=True)
            self._check_program(stmt.body, child)
            if stmt.inverse is not None:
                self._check_program(stmt.inverse, scope)
            return

        child = scope.child(resolved)
        self._check_program(stmt.body, child)
        if stmt.inverse is not None:
            self._check_program(stmt.inverse, scope)

    def _check_path(self, path: PathExpression, scope: _SchemaScope) -> None:
        """Core path validation against the schema."""
        if scope.is_opaque:
            return

        # 'this' with no parts — reference to current context, always valid
        if path.is_this and not path.parts:
            return

        # Check block params first
        if path.parts and path.depth == 0 and not path.is_this:
            first = path.parts[0]
            if first in scope.block_params:
                # Shadowed by block param — skip validation
                return
            # Check parent scopes for block params
            parent = scope.parent
            while parent is not None:
                if first in parent.block_params:  # pragma: no cover
                    return
                parent = parent.parent

        # Walk parent refs
        if path.depth > 0:
            target_scope = scope.get_parent(path.depth)
        else:
            target_scope = scope

        if target_scope.is_opaque:  # pragma: no cover
            return

        current_schema = target_scope.schema

        # Walk path parts
        for i, part in enumerate(path.parts):
            current_schema = self._resolve_ref(current_schema)
            current_schema = self._unwrap_nullable(current_schema)

            field_path = '.'.join(path.parts[: i + 1])
            if path.depth > 0:
                field_path = '../' * path.depth + field_path

            result = self._check_property_access(current_schema, part, field_path)
            if result is None:
                return  # Error already reported, stop walking
            current_schema = result

    def _check_data_path(self, path: PathExpression, scope: _SchemaScope) -> None:
        """Check @data variable access."""
        if not path.parts:  # pragma: no cover
            return

        first = path.parts[0]
        if first == 'root':
            # @root.foo — validate foo against root schema
            remaining_parts = path.parts[1:]
            if not remaining_parts:
                return

            current_schema = self._root_schema
            for i, part in enumerate(remaining_parts):
                current_schema = self._resolve_ref(current_schema)
                current_schema = self._unwrap_nullable(current_schema)
                field_path = '@root.' + '.'.join(remaining_parts[: i + 1])
                result = self._check_property_access(current_schema, part, field_path)
                if result is None:
                    return
                current_schema = result
        # Other @data vars (@index, @key, @first, @last) are always valid

    def _resolve_ref(self, schema: _JsonSchema) -> _JsonSchema:
        """Follow $ref chains, handling circular refs."""
        ref = schema.get('$ref')
        if ref is None:
            return schema

        if not isinstance(ref, str):
            return schema

        if ref in self._resolving_refs:  # pragma: no cover
            # Circular ref — treat as opaque
            return {}

        self._resolving_refs.add(ref)
        try:
            # Extract the definition name from #/$defs/Foo or #/definitions/Foo
            if ref.startswith('#/$defs/'):
                def_name = ref[len('#/$defs/') :]
            elif ref.startswith('#/definitions/'):
                def_name = ref[len('#/definitions/') :]
            else:
                return schema

            if def_name in self._defs:
                resolved = self._defs[def_name]
                # Follow chains
                return self._resolve_ref(resolved)
            return schema
        finally:
            self._resolving_refs.discard(ref)

    def _check_property_access(self, schema: _JsonSchema, property_name: str, field_path: str) -> _JsonSchema | None:
        """Check if a property exists in the schema.

        Returns the property schema if found, None if not found (issue reported).
        """
        resolved = self._resolve_ref(schema)
        resolved = self._unwrap_nullable(resolved)

        # Numeric index on an array schema — descend into items
        if property_name.isdigit() and resolved.get('type') == 'array':
            items = resolved.get('items', {})
            if isinstance(items, dict):
                return self._resolve_ref(cast('_JsonSchema', items))
            return {}

        # Check in anyOf/oneOf
        any_of = resolved.get('anyOf') or resolved.get('oneOf')
        if any_of is not None and isinstance(any_of, list):
            result = self._check_property_in_union(cast('list[_JsonSchema]', any_of), property_name)
            if result is not None:
                return result

        properties: _JsonSchema = resolved.get('properties', {})
        if properties and property_name in properties:
            return self._resolve_ref(cast('_JsonSchema', properties[property_name]))

        # Check additionalProperties
        add_props = resolved.get('additionalProperties')
        if add_props is True:
            return {}
        if isinstance(add_props, dict):
            return self._resolve_ref(cast('_JsonSchema', add_props))

        # Not found
        if properties or resolved.get('type') == 'object':
            required = resolved.get('required', [])
            if isinstance(required, list) and property_name not in required and properties:
                self._add_issue(
                    self._optional_field_severity,
                    f"Field '{property_name}' not found in schema",
                    field_path,
                )
            else:
                self._add_issue(
                    'error',
                    f"Field '{property_name}' not found in schema",
                    field_path,
                )
            return None

        # Schema has no properties defined — could be any type
        if not resolved:
            return {}

        # Schema has a type but no properties
        schema_type = resolved.get('type')
        if schema_type and schema_type != 'object':
            self._add_issue(
                'error',
                f"Cannot access property '{property_name}' on type '{schema_type}'",
                field_path,
            )
            return None

        return {}

    def _check_property_in_union(self, variants: list[_JsonSchema], property_name: str) -> _JsonSchema | None:
        """Check if property exists in any variant of a union type."""
        for variant in variants:
            resolved_variant = self._resolve_ref(variant)
            # Skip null type in union
            if resolved_variant.get('type') == 'null':  # pragma: no cover
                continue
            properties: _JsonSchema = resolved_variant.get('properties', {})
            if properties and property_name in properties:
                return self._resolve_ref(cast('_JsonSchema', properties[property_name]))
            # Check additionalProperties in variant
            add_props = resolved_variant.get('additionalProperties')
            if add_props is True:
                return {}
            if isinstance(add_props, dict):
                return self._resolve_ref(cast('_JsonSchema', add_props))
        return None

    def _check_default_helper(self, stmt: MustacheStatement, scope: _SchemaScope) -> None:
        """Check {{default field "fallback"}} pattern.

        The default helper guards against missing values, so optional field
        severity is downgraded to 'ignore'.
        """
        if not stmt.params:
            return

        # Save and override optional severity
        original_severity = self._optional_field_severity
        self._optional_field_severity = 'ignore'

        self._check_params(stmt.params, scope)
        self._check_params(list(stmt.hash_pairs.values()), scope)

        self._optional_field_severity = original_severity

    def _unwrap_nullable(self, schema: _JsonSchema) -> _JsonSchema:
        """Unwrap pydantic's Optional[X] pattern: anyOf: [{...}, {type: 'null'}]."""
        any_of = schema.get('anyOf')
        if not isinstance(any_of, list) or len(cast('list[Any]', any_of)) != 2:
            return schema

        typed_variants = cast('list[_JsonSchema]', any_of)
        non_null = [v for v in typed_variants if v.get('type') != 'null']
        if len(non_null) == 1:
            return self._resolve_ref(non_null[0])
        return schema

    def _resolve_path_to_schema(self, path: PathExpression, scope: _SchemaScope) -> _JsonSchema | None:
        """Resolve a path expression to its schema node.

        Returns None if the path doesn't resolve (issue already reported via _check_path).
        """
        if scope.is_opaque:
            return {}

        if path.is_this and not path.parts:
            return scope.schema

        # Check block params
        if path.parts and path.depth == 0 and not path.is_this:
            first = path.parts[0]
            if first in scope.block_params:
                return {}
            parent = scope.parent
            while parent is not None:
                if first in parent.block_params:
                    return {}
                parent = parent.parent

        if path.depth > 0:
            target_scope = scope.get_parent(path.depth)
        else:
            target_scope = scope

        if target_scope.is_opaque:  # pragma: no cover
            return {}

        current_schema = target_scope.schema

        for i, part in enumerate(path.parts):
            current_schema = self._resolve_ref(current_schema)
            current_schema = self._unwrap_nullable(current_schema)

            field_path = '.'.join(path.parts[: i + 1])
            if path.depth > 0:
                field_path = '../' * path.depth + field_path

            result = self._check_property_access(current_schema, part, field_path)
            if result is None:
                return None
            current_schema = result

        return current_schema

    def _get_block_param_names(self, stmt: BlockStatement) -> set[str]:
        """Extract block parameter names from a block statement."""
        return set(stmt.block_params)


def check_template_compatibility(
    templates: str | list[str],
    json_schema: _JsonSchema,
    *,
    raise_on_error: bool = False,
    optional_field_severity: IssueSeverity = 'error',
    helpers: set[str] | None = None,
) -> CompatibilityResult:
    """Check template compatibility with a JSON schema.

    Parses the templates, walks their ASTs, and verifies every field reference
    exists in the provided JSON schema.

    Args:
        templates: A single template string or list of template strings.
        json_schema: The JSON schema to validate against (e.g., from Pydantic's
            ``model_json_schema()``).
        raise_on_error: If True, raise ``TemplateSchemaError`` when incompatible.
        optional_field_severity: Severity for fields not found in the schema when the
            schema has properties but the field is not in ``required``. Defaults to ERROR.
        helpers: Additional helper names to treat as known (beyond built-in helpers).

    Returns:
        A ``CompatibilityResult`` with any issues found.

    Raises:
        TemplateSchemaError: If ``raise_on_error`` is True and there are ERROR-level issues.
    """
    if isinstance(templates, str):
        template_list = [templates]
    else:
        template_list = templates

    programs = [parse(t) for t in template_list]

    checker = _SchemaChecker(
        root_schema=json_schema,
        optional_field_severity=optional_field_severity,
        helpers=helpers or set(),
    )
    issues = checker.check(programs)

    result = CompatibilityResult(issues=issues)

    if raise_on_error and not result.is_compatible:
        error_issues = [i for i in issues if i.severity == 'error']
        message_parts = [f'{len(error_issues)} error(s) found:']
        for issue in error_issues:
            message_parts.append(f'  - {issue.field_path}: {issue.message}')
        raise TemplateSchemaError('\n'.join(message_parts), result=result)

    return result
