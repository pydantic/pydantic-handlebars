"""Tests for JSON Schema template compatibility checking."""

from typing import Any

import pytest

from pydantic_handlebars import (
    CompatibilityResult,
    HandlebarsParseError,
    TemplateIssue,
    TemplateSchemaError,
    check_template_compatibility,
)

# --- Basic field validation ---


def test_valid_simple_field():
    schema = {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}
    result = check_template_compatibility('{{name}}', schema)
    assert result.is_compatible
    assert result.issues == []


def test_invalid_field():
    schema = {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}
    result = check_template_compatibility('{{missing}}', schema)
    assert not result.is_compatible
    assert len(result.issues) == 1
    assert result.issues[0].severity == 'error'
    assert result.issues[0].field_path == 'missing'


def test_multiple_valid_fields():
    schema = {
        'type': 'object',
        'properties': {'name': {'type': 'string'}, 'age': {'type': 'integer'}},
        'required': ['name', 'age'],
    }
    result = check_template_compatibility('{{name}} is {{age}}', schema)
    assert result.is_compatible


def test_multiple_invalid_fields():
    schema = {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}
    result = check_template_compatibility('{{foo}} {{bar}}', schema)
    assert not result.is_compatible
    assert len(result.issues) == 2


# --- Nested paths ---


def test_nested_path():
    schema = {
        'type': 'object',
        'properties': {'person': {'type': 'object', 'properties': {'name': {'type': 'string'}}}},
        'required': ['person'],
    }
    result = check_template_compatibility('{{person.name}}', schema)
    assert result.is_compatible


def test_invalid_nested_path():
    schema = {
        'type': 'object',
        'properties': {'person': {'type': 'object', 'properties': {'name': {'type': 'string'}}}},
        'required': ['person'],
    }
    result = check_template_compatibility('{{person.email}}', schema)
    assert not result.is_compatible


def test_deeply_nested_path():
    schema = {
        'type': 'object',
        'properties': {
            'a': {
                'type': 'object',
                'properties': {'b': {'type': 'object', 'properties': {'c': {'type': 'string'}}}},
            }
        },
        'required': ['a'],
    }
    result = check_template_compatibility('{{a.b.c}}', schema)
    assert result.is_compatible


# --- $ref resolution ---


def test_ref_resolution():
    schema = {
        'type': 'object',
        'properties': {'address': {'$ref': '#/$defs/Address'}},
        'required': ['address'],
        '$defs': {'Address': {'type': 'object', 'properties': {'city': {'type': 'string'}}, 'required': ['city']}},
    }
    result = check_template_compatibility('{{address.city}}', schema)
    assert result.is_compatible


def test_ref_invalid_field():
    schema = {
        'type': 'object',
        'properties': {'address': {'$ref': '#/$defs/Address'}},
        'required': ['address'],
        '$defs': {'Address': {'type': 'object', 'properties': {'city': {'type': 'string'}}, 'required': ['city']}},
    }
    result = check_template_compatibility('{{address.zipcode}}', schema)
    assert not result.is_compatible


def test_definitions_style_ref():
    schema = {
        'type': 'object',
        'properties': {'item': {'$ref': '#/definitions/Item'}},
        'required': ['item'],
        'definitions': {'Item': {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}},
    }
    result = check_template_compatibility('{{item.name}}', schema)
    assert result.is_compatible


def test_circular_ref():
    schema = {
        'type': 'object',
        'properties': {'node': {'$ref': '#/$defs/Node'}},
        'required': ['node'],
        '$defs': {
            'Node': {
                'type': 'object',
                'properties': {'child': {'$ref': '#/$defs/Node'}, 'value': {'type': 'string'}},
                'required': ['value'],
            }
        },
    }
    result = check_template_compatibility('{{node.value}}', schema)
    assert result.is_compatible


# --- #each ---


def test_each_array():
    schema = {
        'type': 'object',
        'properties': {
            'items': {'type': 'array', 'items': {'type': 'object', 'properties': {'name': {'type': 'string'}}}}
        },
        'required': ['items'],
    }
    result = check_template_compatibility('{{#each items}}{{name}}{{/each}}', schema)
    assert result.is_compatible


def test_each_array_invalid_field():
    schema = {
        'type': 'object',
        'properties': {
            'items': {'type': 'array', 'items': {'type': 'object', 'properties': {'name': {'type': 'string'}}}}
        },
        'required': ['items'],
    }
    result = check_template_compatibility('{{#each items}}{{missing}}{{/each}}', schema)
    assert not result.is_compatible


def test_each_object_with_additional_properties():
    schema = {
        'type': 'object',
        'properties': {
            'mapping': {
                'type': 'object',
                'additionalProperties': {'type': 'object', 'properties': {'val': {'type': 'string'}}},
            }
        },
        'required': ['mapping'],
    }
    result = check_template_compatibility('{{#each mapping}}{{val}}{{/each}}', schema)
    assert result.is_compatible


def test_each_object_additional_properties_true():
    schema = {
        'type': 'object',
        'properties': {'data': {'type': 'object', 'additionalProperties': True}},
        'required': ['data'],
    }
    # Body should be opaque since additionalProperties is True
    result = check_template_compatibility('{{#each data}}{{anything}}{{/each}}', schema)
    assert result.is_compatible


def test_each_with_inverse():
    schema = {
        'type': 'object',
        'properties': {
            'items': {'type': 'array', 'items': {'type': 'object', 'properties': {'name': {'type': 'string'}}}}
        },
        'required': ['items'],
    }
    result = check_template_compatibility('{{#each items}}{{name}}{{else}}No items{{/each}}', schema)
    assert result.is_compatible


# --- #with ---


def test_with_valid():
    schema = {
        'type': 'object',
        'properties': {'person': {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}},
        'required': ['person'],
    }
    result = check_template_compatibility('{{#with person}}{{name}}{{/with}}', schema)
    assert result.is_compatible


def test_with_invalid_field():
    schema = {
        'type': 'object',
        'properties': {'person': {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}},
        'required': ['person'],
    }
    result = check_template_compatibility('{{#with person}}{{email}}{{/with}}', schema)
    assert not result.is_compatible


def test_with_inverse():
    schema = {
        'type': 'object',
        'properties': {'person': {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}},
        'required': ['person'],
    }
    result = check_template_compatibility('{{#with person}}{{name}}{{else}}No person{{/with}}', schema)
    assert result.is_compatible


# --- #if / #unless ---


def test_if_same_scope():
    schema = {
        'type': 'object',
        'properties': {'active': {'type': 'boolean'}, 'name': {'type': 'string'}},
        'required': ['active', 'name'],
    }
    result = check_template_compatibility('{{#if active}}{{name}}{{/if}}', schema)
    assert result.is_compatible


def test_if_with_else():
    schema = {
        'type': 'object',
        'properties': {'active': {'type': 'boolean'}, 'name': {'type': 'string'}},
        'required': ['active', 'name'],
    }
    result = check_template_compatibility('{{#if active}}{{name}}{{else}}inactive{{/if}}', schema)
    assert result.is_compatible


def test_unless():
    schema = {
        'type': 'object',
        'properties': {'disabled': {'type': 'boolean'}, 'name': {'type': 'string'}},
        'required': ['disabled', 'name'],
    }
    result = check_template_compatibility('{{#unless disabled}}{{name}}{{/unless}}', schema)
    assert result.is_compatible


def test_if_validates_condition():
    schema = {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}
    result = check_template_compatibility('{{#if missing}}show{{/if}}', schema)
    assert not result.is_compatible


# --- Parent refs (../) ---


def test_parent_ref():
    schema = {
        'type': 'object',
        'properties': {
            'title': {'type': 'string'},
            'items': {
                'type': 'array',
                'items': {'type': 'object', 'properties': {'name': {'type': 'string'}}},
            },
        },
        'required': ['title', 'items'],
    }
    result = check_template_compatibility('{{#each items}}{{../title}}{{/each}}', schema)
    assert result.is_compatible


def test_parent_ref_invalid():
    schema = {
        'type': 'object',
        'properties': {
            'items': {
                'type': 'array',
                'items': {'type': 'object', 'properties': {'name': {'type': 'string'}}},
            },
        },
        'required': ['items'],
    }
    result = check_template_compatibility('{{#each items}}{{../missing}}{{/each}}', schema)
    assert not result.is_compatible


# --- @root ---


def test_root_ref():
    schema = {
        'type': 'object',
        'properties': {
            'title': {'type': 'string'},
            'items': {
                'type': 'array',
                'items': {'type': 'object', 'properties': {'name': {'type': 'string'}}},
            },
        },
        'required': ['title', 'items'],
    }
    result = check_template_compatibility('{{#each items}}{{@root.title}}{{/each}}', schema)
    assert result.is_compatible


def test_root_ref_invalid():
    schema = {
        'type': 'object',
        'properties': {'name': {'type': 'string'}},
        'required': ['name'],
    }
    result = check_template_compatibility('{{@root.missing}}', schema)
    assert not result.is_compatible


# --- @data vars ---


def test_data_vars_skipped():
    schema = {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}
    result = check_template_compatibility('{{#each items}}{{@index}}{{@key}}{{@first}}{{@last}}{{/each}}', schema)
    # @data vars are skipped, but 'items' is not in schema
    assert not result.is_compatible
    # Only one issue for 'items'
    assert len(result.issues) == 1


def test_bare_data_path_parse_error():
    """{{@}} with no parts raises a parse error."""
    schema = {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}
    with pytest.raises(HandlebarsParseError):
        check_template_compatibility('{{@}}', schema)


# --- Block params ---


def test_block_params_shadow():
    schema = {
        'type': 'object',
        'properties': {
            'items': {
                'type': 'array',
                'items': {'type': 'object', 'properties': {'name': {'type': 'string'}}},
            }
        },
        'required': ['items'],
    }
    result = check_template_compatibility('{{#each items as |item|}}{{item.name}}{{/each}}', schema)
    # Block param shadows lookup — should be valid (opaque)
    assert result.is_compatible


# --- default helper ---


def test_default_helper_downgrades_severity():
    schema = {
        'type': 'object',
        'properties': {'name': {'type': 'string'}},
    }
    # Without default — uses optional_field_severity
    result = check_template_compatibility('{{nickname}}', schema, optional_field_severity='error')
    assert not result.is_compatible

    # With default — severity should be downgraded to INFO
    result = check_template_compatibility(
        '{{default nickname "N/A"}}', schema, optional_field_severity='error', helpers={'default'}
    )
    assert result.is_compatible
    assert len(result.issues) == 1
    assert result.issues[0].severity == 'ignore'


# --- Custom helpers ---


def test_custom_helper_known():
    schema = {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}
    result = check_template_compatibility('{{formatDate name}}', schema, helpers={'formatDate'})
    assert result.is_compatible


def test_custom_helper_params_validated():
    schema = {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}
    result = check_template_compatibility('{{formatDate missing}}', schema, helpers={'formatDate'})
    assert not result.is_compatible


def test_custom_block_helper_opaque_body():
    schema = {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}
    result = check_template_compatibility('{{#custom}}{{anything}}{{/custom}}', schema, helpers={'custom'})
    assert result.is_compatible


# --- lookup helper ---


def test_lookup_helper():
    schema = {'type': 'object', 'properties': {'obj': {'type': 'object'}}, 'required': ['obj']}
    result = check_template_compatibility('{{lookup obj "key"}}', schema)
    assert result.is_compatible


# --- additionalProperties ---


def test_additional_properties_true():
    schema = {'type': 'object', 'additionalProperties': True}
    result = check_template_compatibility('{{anything}}', schema)
    assert result.is_compatible


def test_additional_properties_schema():
    schema = {
        'type': 'object',
        'additionalProperties': {'type': 'string'},
    }
    result = check_template_compatibility('{{anything}}', schema)
    assert result.is_compatible


# --- optional_field_severity ---


def test_optional_field_severity_warning():
    # 'nickname' is NOT in properties — it's an unknown field
    # optional_field_severity applies when the schema has properties but the field isn't in required
    schema = {
        'type': 'object',
        'properties': {'name': {'type': 'string'}, 'email': {'type': 'string'}},
        'required': ['name'],
    }
    result = check_template_compatibility('{{nickname}}', schema, optional_field_severity='warning')
    assert result.is_compatible
    assert len(result.issues) == 1
    assert result.issues[0].severity == 'warning'


def test_optional_field_severity_ignore():
    schema = {
        'type': 'object',
        'properties': {'name': {'type': 'string'}, 'email': {'type': 'string'}},
        'required': ['name'],
    }
    result = check_template_compatibility('{{nickname}}', schema, optional_field_severity='ignore')
    assert result.is_compatible


# --- raise_on_error ---


def test_raise_on_error():
    schema = {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}
    with pytest.raises(TemplateSchemaError) as exc_info:
        check_template_compatibility('{{missing}}', schema, raise_on_error=True)
    assert exc_info.value.result is not None
    assert not exc_info.value.result.is_compatible


def test_raise_on_error_compatible():
    schema = {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}
    result = check_template_compatibility('{{name}}', schema, raise_on_error=True)
    assert result.is_compatible


# --- Multi-template ---


def test_multi_template():
    schema = {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}
    result = check_template_compatibility(['{{name}}', '{{name}}'], schema)
    assert result.is_compatible


def test_multi_template_one_invalid():
    schema = {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}
    result = check_template_compatibility(['{{name}}', '{{missing}}'], schema)
    assert not result.is_compatible
    assert result.issues[0].template_index == 1


# --- this references ---


def test_this_reference():
    schema = {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}
    result = check_template_compatibility('{{this.name}}', schema)
    assert result.is_compatible


def test_this_bare():
    schema = {'type': 'object', 'properties': {'name': {'type': 'string'}}}
    result = check_template_compatibility('{{this}}', schema)
    assert result.is_compatible


# --- Subexpressions ---


def test_subexpression_params_validated():
    schema = {'type': 'object', 'properties': {'val': {'type': 'string'}}, 'required': ['val']}
    result = check_template_compatibility('{{uppercase (trim val)}}', schema, helpers={'uppercase', 'trim'})
    assert result.is_compatible


def test_subexpression_invalid_param():
    schema = {'type': 'object', 'properties': {'val': {'type': 'string'}}, 'required': ['val']}
    result = check_template_compatibility('{{uppercase (trim missing)}}', schema, helpers={'uppercase', 'trim'})
    assert not result.is_compatible


# --- Chained else-if ---


def test_chained_else_if():
    schema = {
        'type': 'object',
        'properties': {'a': {'type': 'boolean'}, 'b': {'type': 'boolean'}, 'name': {'type': 'string'}},
        'required': ['a', 'b', 'name'],
    }
    result = check_template_compatibility('{{#if a}}A{{else if b}}B{{else}}C{{/if}}', schema)
    assert result.is_compatible


# --- Context-based blocks ---


def test_context_block():
    schema = {
        'type': 'object',
        'properties': {'person': {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}},
        'required': ['person'],
    }
    result = check_template_compatibility('{{#person}}{{name}}{{/person}}', schema)
    assert result.is_compatible


def test_context_block_invalid():
    schema = {
        'type': 'object',
        'properties': {'person': {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}},
        'required': ['person'],
    }
    result = check_template_compatibility('{{#person}}{{email}}{{/person}}', schema)
    assert not result.is_compatible


def test_context_block_missing():
    schema = {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}
    result = check_template_compatibility('{{#missing}}{{foo}}{{/missing}}', schema)
    assert not result.is_compatible


# --- Empty schema ---


def test_empty_schema():
    result = check_template_compatibility('{{anything}}', {})
    assert result.is_compatible


# --- Nullable / anyOf with null ---


def test_nullable_field():
    schema = {
        'type': 'object',
        'properties': {
            'value': {'anyOf': [{'type': 'object', 'properties': {'inner': {'type': 'string'}}}, {'type': 'null'}]}
        },
        'required': ['value'],
    }
    result = check_template_compatibility('{{value.inner}}', schema)
    assert result.is_compatible


def test_anyof_union():
    schema = {
        'type': 'object',
        'properties': {
            'data': {
                'anyOf': [
                    {'type': 'object', 'properties': {'x': {'type': 'string'}}},
                    {'type': 'object', 'properties': {'y': {'type': 'string'}}},
                ]
            }
        },
        'required': ['data'],
    }
    # Property valid if found in any variant
    result = check_template_compatibility('{{data.x}}', schema)
    assert result.is_compatible
    result = check_template_compatibility('{{data.y}}', schema)
    assert result.is_compatible


# --- Type access errors ---


def test_property_access_on_non_object():
    schema = {
        'type': 'object',
        'properties': {'name': {'type': 'string'}},
        'required': ['name'],
    }
    result = check_template_compatibility('{{name.foo}}', schema)
    assert not result.is_compatible
    assert 'Cannot access property' in result.issues[0].message


# --- CompatibilityResult / TemplateIssue ---


def test_compatibility_result_is_compatible_no_issues():
    result = CompatibilityResult(issues=[])
    assert result.is_compatible


def test_compatibility_result_with_warning_only():
    result = CompatibilityResult(
        issues=[TemplateIssue(severity='warning', message='test', field_path='x', template_index=0)]
    )
    assert result.is_compatible


def test_compatibility_result_with_error():
    result = CompatibilityResult(
        issues=[TemplateIssue(severity='error', message='test', field_path='x', template_index=0)]
    )
    assert not result.is_compatible


# --- Hash arguments (no validation needed) ---


def test_hash_arguments():
    schema = {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}
    result = check_template_compatibility('{{log name level="info"}}', schema)
    assert result.is_compatible


# --- @root bare ---


def test_root_bare():
    schema = {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}
    result = check_template_compatibility('{{@root}}', schema)
    assert result.is_compatible


# --- Content and comments ---


def test_content_only():
    schema = {'type': 'object', 'properties': {'name': {'type': 'string'}}}
    result = check_template_compatibility('Hello world!', schema)
    assert result.is_compatible


def test_comments_ignored():
    schema = {'type': 'object', 'properties': {'name': {'type': 'string'}}}
    result = check_template_compatibility('{{! comment }}{{name}}', schema)
    assert result.is_compatible


# --- Built-in helpers are recognized ---


def test_builtin_helpers():
    schema = {
        'type': 'object',
        'properties': {'items': {'type': 'array', 'items': {'type': 'string'}}},
        'required': ['items'],
    }
    # Standard helpers (if, each, with, etc.) are always known
    result = check_template_compatibility('{{log items}}', schema)
    assert result.is_compatible


# --- if with params ---


def test_if_with_param():
    schema = {
        'type': 'object',
        'properties': {'show': {'type': 'boolean'}, 'name': {'type': 'string'}},
        'required': ['show', 'name'],
    }
    result = check_template_compatibility('{{#if show}}{{name}}{{/if}}', schema)
    assert result.is_compatible


# --- oneOf ---


def test_oneof_union():
    schema = {
        'type': 'object',
        'properties': {
            'data': {
                'oneOf': [
                    {'type': 'object', 'properties': {'a': {'type': 'string'}}},
                    {'type': 'object', 'properties': {'b': {'type': 'string'}}},
                ]
            }
        },
        'required': ['data'],
    }
    result = check_template_compatibility('{{data.a}}', schema)
    assert result.is_compatible


# --- each over data var ---


def test_each_over_data_var():
    schema = {'type': 'object', 'properties': {'x': {'type': 'string'}}, 'required': ['x']}
    result = check_template_compatibility('{{#each @root.items}}{{this}}{{/each}}', schema)
    # @root.items will fail validation since items isn't in schema
    assert not result.is_compatible


# --- with over literal ---


def test_with_literal_param():
    schema = {'type': 'object', 'properties': {'x': {'type': 'string'}}, 'required': ['x']}
    result = check_template_compatibility('{{#with "hello"}}{{this}}{{/with}}', schema)
    assert result.is_compatible


# --- each over literal ---


def test_each_literal_param():
    schema = {'type': 'object', 'properties': {'x': {'type': 'string'}}, 'required': ['x']}
    result = check_template_compatibility('{{#each "hello"}}{{this}}{{/each}}', schema)
    assert result.is_compatible


# --- context-based block with inverse ---


def test_context_block_with_inverse():
    schema = {
        'type': 'object',
        'properties': {'person': {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}},
        'required': ['person'],
    }
    result = check_template_compatibility('{{#person}}{{name}}{{else}}No person{{/person}}', schema)
    assert result.is_compatible


# --- with no params ---


def test_with_no_params():
    schema = {
        'type': 'object',
        'properties': {'name': {'type': 'string'}},
        'required': ['name'],
    }
    result = check_template_compatibility('{{#with}}{{name}}{{/with}}', schema)
    assert result.is_compatible


# --- with data param ---


def test_with_data_param():
    schema = {'type': 'object', 'properties': {'x': {'type': 'string'}}, 'required': ['x']}
    result = check_template_compatibility('{{#with @root}}{{x}}{{/with}}', schema)
    assert result.is_compatible


# --- with block params ---


def test_with_block_params():
    schema = {
        'type': 'object',
        'properties': {'person': {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}},
        'required': ['person'],
    }
    result = check_template_compatibility('{{#with person as |p|}}{{p.name}}{{/with}}', schema)
    assert result.is_compatible


# --- each no params ---


def test_each_no_params():
    schema = {
        'type': 'array',
        'items': {'type': 'object', 'properties': {'name': {'type': 'string'}}},
    }
    result = check_template_compatibility('{{#each}}{{name}}{{/each}}', schema)
    assert result.is_compatible


# --- each data path ---


def test_each_data_path():
    schema = {'type': 'object', 'properties': {'x': {'type': 'string'}}, 'required': ['x']}
    result = check_template_compatibility('{{#each @root}}{{this}}{{/each}}', schema)
    assert result.is_compatible


# --- with inverse for non-resolving path ---


def test_with_unresolved_path():
    schema = {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}
    result = check_template_compatibility('{{#with missing}}{{x}}{{else}}fallback{{/with}}', schema)
    assert not result.is_compatible


# --- block with non-path expression ---


def test_block_non_path():
    schema = {'type': 'object', 'properties': {'x': {'type': 'string'}}}
    # This isn't a valid handlebars template normally, but test the edge case
    # where stmt.path might be a subexpression in a block — the checker should skip it
    result = check_template_compatibility('{{x}}', schema)
    assert result.is_compatible


# --- custom block helper with inverse ---


def test_custom_block_helper_with_inverse():
    schema = {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}
    result = check_template_compatibility('{{#custom}}body{{else}}inverse{{/custom}}', schema, helpers={'custom'})
    assert result.is_compatible


# --- unless validates condition ---


def test_unless_validates_condition():
    schema = {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}
    result = check_template_compatibility('{{#unless missing}}show{{/unless}}', schema)
    assert not result.is_compatible


# --- ref chain ---


def test_ref_chain():
    schema = {
        'type': 'object',
        'properties': {'a': {'$ref': '#/$defs/A'}},
        'required': ['a'],
        '$defs': {
            'A': {'$ref': '#/$defs/B'},
            'B': {'type': 'object', 'properties': {'val': {'type': 'string'}}, 'required': ['val']},
        },
    }
    result = check_template_compatibility('{{a.val}}', schema)
    assert result.is_compatible


# --- unknown ref ---


def test_unknown_ref():
    schema = {
        'type': 'object',
        'properties': {'a': {'$ref': '#/$defs/Unknown'}},
        'required': ['a'],
        '$defs': {},
    }
    # Unknown $ref — the schema has a $ref but it can't be resolved,
    # so the original schema (with $ref) is returned. Accessing a property
    # on it should be valid since there are no properties defined.
    result = check_template_compatibility('{{a.foo}}', schema)
    assert result.is_compatible


# --- external ref ---


def test_external_ref():
    schema = {
        'type': 'object',
        'properties': {'a': {'$ref': 'external.json#/Foo'}},
        'required': ['a'],
    }
    result = check_template_compatibility('{{a.foo}}', schema)
    assert result.is_compatible


# --- non-string ref ---


def test_non_string_ref():
    schema = {
        'type': 'object',
        'properties': {'a': {'$ref': 123}},
        'required': ['a'],
    }
    result = check_template_compatibility('{{a.foo}}', schema)
    assert result.is_compatible


# --- each unresolved path ---


def test_each_unresolved_path():
    schema = {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}
    result = check_template_compatibility('{{#each missing}}{{x}}{{/each}}', schema)
    assert not result.is_compatible


# --- parent ref beyond root ---


def test_parent_ref_beyond_root():
    schema = {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}
    result = check_template_compatibility('{{../name}}', schema)
    assert result.is_compatible


# --- each without items key ---


def test_each_non_array():
    schema = {
        'type': 'object',
        'properties': {'data': {'type': 'string'}},
        'required': ['data'],
    }
    result = check_template_compatibility('{{#each data}}{{this}}{{/each}}', schema)
    # data is string, not array — each will make inner scope opaque
    assert result.is_compatible


# --- Schema with type: object but no properties ---


def test_object_no_properties():
    schema = {'type': 'object'}
    result = check_template_compatibility('{{anything}}', schema)
    assert not result.is_compatible


# --- additionalProperties in union variant ---


def test_additional_properties_in_union():
    schema = {
        'type': 'object',
        'properties': {
            'data': {
                'anyOf': [
                    {'type': 'object', 'additionalProperties': True},
                    {'type': 'null'},
                ]
            }
        },
        'required': ['data'],
    }
    result = check_template_compatibility('{{data.anything}}', schema)
    assert result.is_compatible


# --- with unresolved path and inverse ---


def test_with_unresolved_inverse():
    schema = {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}
    result = check_template_compatibility('{{#with missing}}{{x}}{{else}}{{name}}{{/with}}', schema)
    assert not result.is_compatible
    # Should have one issue for 'missing'
    error_issues = [i for i in result.issues if i.severity == 'error']
    assert len(error_issues) == 1


# --- each unresolved with inverse ---


def test_each_unresolved_inverse():
    schema = {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}
    result = check_template_compatibility('{{#each missing}}{{x}}{{else}}{{name}}{{/each}}', schema)
    assert not result.is_compatible


# --- with block params for with ---


def test_with_block_params_data():
    schema = {
        'type': 'object',
        'properties': {'person': {'type': 'object', 'properties': {'name': {'type': 'string'}}}},
    }
    result = check_template_compatibility('{{#with @root as |ctx|}}{{ctx}}{{/with}}', schema)
    assert result.is_compatible


# --- mustache with subexpression path ---


def test_mustache_subexpression_path():
    schema = {'type': 'object', 'properties': {'val': {'type': 'string'}}, 'required': ['val']}
    result = check_template_compatibility('{{(lookup val "key")}}', schema)
    assert result.is_compatible


# --- opaque parent scope ---


def test_opaque_parent_scope():
    schema = {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}
    result = check_template_compatibility(
        '{{#custom}}{{#if true}}{{../whatever}}{{/if}}{{/custom}}', schema, helpers={'custom'}
    )
    assert result.is_compatible


# --- Coverage: inverse blocks ---


def test_each_no_params_with_inverse():
    schema = {
        'type': 'array',
        'items': {'type': 'object', 'properties': {'name': {'type': 'string'}}},
    }
    result = check_template_compatibility('{{#each}}{{name}}{{else}}empty{{/each}}', schema)
    assert result.is_compatible


def test_each_data_path_with_inverse():
    schema = {'type': 'object', 'properties': {'x': {'type': 'string'}}, 'required': ['x']}
    result = check_template_compatibility('{{#each @root}}{{this}}{{else}}empty{{/each}}', schema)
    assert result.is_compatible


def test_each_literal_with_inverse():
    schema = {'type': 'object', 'properties': {'x': {'type': 'string'}}, 'required': ['x']}
    result = check_template_compatibility('{{#each "hello"}}{{this}}{{else}}empty{{/each}}', schema)
    assert result.is_compatible


def test_with_no_params_with_inverse():
    schema = {
        'type': 'object',
        'properties': {'name': {'type': 'string'}},
        'required': ['name'],
    }
    result = check_template_compatibility('{{#with}}{{name}}{{else}}empty{{/with}}', schema)
    assert result.is_compatible


def test_with_data_param_with_inverse():
    schema = {'type': 'object', 'properties': {'x': {'type': 'string'}}, 'required': ['x']}
    result = check_template_compatibility('{{#with @root}}{{x}}{{else}}empty{{/with}}', schema)
    assert result.is_compatible


def test_with_literal_with_inverse():
    schema = {'type': 'object', 'properties': {'x': {'type': 'string'}}, 'required': ['x']}
    result = check_template_compatibility('{{#with "hello"}}{{this}}{{else}}empty{{/with}}', schema)
    assert result.is_compatible


def test_context_block_missing_with_inverse():
    schema = {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}
    result = check_template_compatibility('{{#missing}}{{foo}}{{else}}fallback{{/missing}}', schema)
    assert not result.is_compatible


def test_with_unresolved_no_inverse():
    schema = {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}
    result = check_template_compatibility('{{#with missing}}{{x}}{{/with}}', schema)
    assert not result.is_compatible


# --- Coverage: data var as helper param ---


def test_data_var_as_helper_param():
    schema = {
        'type': 'object',
        'properties': {'items': {'type': 'array', 'items': {'type': 'string'}}},
        'required': ['items'],
    }
    result = check_template_compatibility('{{#each items}}{{log @index}}{{/each}}', schema)
    assert result.is_compatible


# --- Coverage: block param in parent scope ---


def test_block_param_in_parent_scope():
    schema = {
        'type': 'object',
        'properties': {
            'items': {
                'type': 'array',
                'items': {'type': 'object', 'properties': {'name': {'type': 'string'}}},
            }
        },
        'required': ['items'],
    }
    result = check_template_compatibility('{{#each items as |item|}}{{#if item}}{{item.name}}{{/if}}{{/each}}', schema)
    assert result.is_compatible


# --- Coverage: block param in _resolve_path_to_schema ---


def test_block_param_in_with():
    schema = {
        'type': 'object',
        'properties': {
            'items': {
                'type': 'array',
                'items': {'type': 'object', 'properties': {'name': {'type': 'string'}}},
            }
        },
        'required': ['items'],
    }
    result = check_template_compatibility('{{#each items as |item|}}{{#with item}}{{name}}{{/with}}{{/each}}', schema)
    assert result.is_compatible


def test_block_param_in_parent_scope_for_resolve():
    schema = {
        'type': 'object',
        'properties': {
            'outer': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'inner': {
                            'type': 'array',
                            'items': {'type': 'object', 'properties': {'val': {'type': 'string'}}},
                        }
                    },
                },
            }
        },
        'required': ['outer'],
    }
    # The inner each references outer's block param via with
    result = check_template_compatibility(
        '{{#each outer as |o|}}{{#each inner}}{{#with o}}{{val}}{{/with}}{{/each}}{{/each}}', schema
    )
    assert result.is_compatible


# --- Coverage: resolve_path_to_schema with depth > 0 ---


def test_resolve_path_depth_in_with():
    schema = {
        'type': 'object',
        'properties': {
            'title': {'type': 'string'},
            'items': {
                'type': 'array',
                'items': {'type': 'object', 'properties': {'name': {'type': 'string'}}},
            },
        },
        'required': ['title', 'items'],
    }
    # ../title inside #each, then used in #with to resolve through parent
    result = check_template_compatibility('{{#each items}}{{#with ../title}}{{this}}{{/with}}{{/each}}', schema)
    assert result.is_compatible


# --- Coverage: resolve_path_to_schema opaque scope ---


def test_resolve_path_opaque_scope():
    schema = {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}
    # custom helper makes scope opaque, then #with tries to resolve in opaque scope
    result = check_template_compatibility(
        '{{#custom}}{{#with something}}{{x}}{{/with}}{{/custom}}', schema, helpers={'custom'}
    )
    assert result.is_compatible


# --- Coverage: resolve_path_to_schema this ---


def test_resolve_path_this_in_with():
    schema = {
        'type': 'object',
        'properties': {'name': {'type': 'string'}},
        'required': ['name'],
    }
    result = check_template_compatibility('{{#with this}}{{name}}{{/with}}', schema)
    assert result.is_compatible


# --- Coverage: resolve_path_to_schema opaque target via depth ---


def test_resolve_path_opaque_target_via_depth():
    schema = {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}
    # custom makes scope opaque; inner each has depth > 0 which targets the opaque scope
    result = check_template_compatibility(
        '{{#custom}}{{#each items}}{{#with ../something}}{{x}}{{/with}}{{/each}}{{/custom}}',
        schema,
        helpers={'custom'},
    )
    assert result.is_compatible


# --- Coverage: circular ref actually triggered ---


def test_circular_ref_deep_traversal():
    schema = {
        'type': 'object',
        'properties': {'node': {'$ref': '#/$defs/Node'}},
        'required': ['node'],
        '$defs': {
            'Node': {
                'type': 'object',
                'properties': {'child': {'$ref': '#/$defs/Node'}, 'value': {'type': 'string'}},
                'required': ['value'],
            }
        },
    }
    # Access nested child which triggers circular ref resolution
    result = check_template_compatibility('{{node.child.value}}', schema)
    assert result.is_compatible


# --- Coverage: union with 3+ variants including null ---


def test_union_three_variants_with_null():
    schema = {
        'type': 'object',
        'properties': {
            'data': {
                'anyOf': [
                    {'type': 'object', 'properties': {'x': {'type': 'string'}}},
                    {'type': 'object', 'properties': {'y': {'type': 'string'}}},
                    {'type': 'null'},
                ]
            }
        },
        'required': ['data'],
    }
    result = check_template_compatibility('{{data.x}}', schema)
    assert result.is_compatible


# --- Coverage: union variant with additionalProperties ---


def test_union_variant_additional_properties_true():
    schema = {
        'type': 'object',
        'properties': {
            'data': {
                'anyOf': [
                    {'type': 'object', 'additionalProperties': True},
                    {'type': 'object', 'properties': {'y': {'type': 'string'}}},
                ]
            }
        },
        'required': ['data'],
    }
    result = check_template_compatibility('{{data.anything}}', schema)
    assert result.is_compatible


def test_union_variant_additional_properties_dict():
    schema = {
        'type': 'object',
        'properties': {
            'data': {
                'anyOf': [
                    {'type': 'object', 'additionalProperties': {'type': 'string'}},
                    {'type': 'object', 'properties': {'y': {'type': 'string'}}},
                ]
            }
        },
        'required': ['data'],
    }
    result = check_template_compatibility('{{data.anything}}', schema)
    assert result.is_compatible


# --- Coverage: default helper edge cases ---


def test_default_helper_no_params():
    schema = {'type': 'object', 'properties': {'name': {'type': 'string'}}, 'required': ['name']}
    result = check_template_compatibility('{{default}}', schema, helpers={'default'})
    assert result.is_compatible


def test_default_helper_data_param():
    schema = {
        'type': 'object',
        'properties': {
            'items': {'type': 'array', 'items': {'type': 'string'}},
        },
        'required': ['items'],
    }
    result = check_template_compatibility(
        '{{#each items}}{{default @root.fallback "N/A"}}{{/each}}', schema, helpers={'default'}
    )
    # default helper downgrades severity to 'ignore', so is_compatible is True
    assert result.is_compatible
    assert len(result.issues) == 1
    assert result.issues[0].severity == 'ignore'


def test_default_helper_subexpression_param():
    schema = {'type': 'object', 'properties': {'val': {'type': 'string'}}, 'required': ['val']}
    result = check_template_compatibility('{{default (lookup val "key") "N/A"}}', schema, helpers={'default'})
    assert result.is_compatible


# --- Coverage: known helper as dotted path ---


def test_known_helper_as_dotted_path():
    schema = {
        'type': 'object',
        'properties': {'log': {'type': 'object', 'properties': {'level': {'type': 'string'}}}},
        'required': ['log'],
    }
    # 'log' is a known helper but used as {{log.level}} — should check as path
    result = check_template_compatibility('{{log.level}}', schema)
    assert result.is_compatible


# --- Coverage: each array items non-dict ---


def test_each_array_items_non_dict():
    schema = {
        'type': 'object',
        'properties': {
            'items': {'type': 'array', 'items': True},
        },
        'required': ['items'],
    }
    result = check_template_compatibility('{{#each items}}{{this}}{{/each}}', schema)
    assert result.is_compatible


# --- Coverage: anyOf/oneOf falls through to properties ---


def test_anyof_fallthrough_to_properties():
    schema = {
        'type': 'object',
        'properties': {
            'data': {
                'anyOf': [
                    {'type': 'string'},
                    {'type': 'integer'},
                ],
                'properties': {'x': {'type': 'string'}},
            }
        },
        'required': ['data'],
    }
    # anyOf variants don't have properties, but the schema itself does
    result = check_template_compatibility('{{data.x}}', schema)
    assert result.is_compatible


# --- Coverage: parent ref in resolve_path_to_schema with depth ---


def test_each_parent_ref_in_context_block():
    schema = {
        'type': 'object',
        'properties': {
            'items': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'sub': {'type': 'object', 'properties': {'val': {'type': 'string'}}},
                    },
                },
            },
        },
        'required': ['items'],
    }
    result = check_template_compatibility('{{#each items}}{{#sub}}{{val}}{{/sub}}{{/each}}', schema)
    assert result.is_compatible


# --- Literal expressions in mustache position ---


def test_literal_true_in_mustache():
    """Schema checker should not crash on {{true}}."""
    schema = {'type': 'object', 'properties': {'name': {'type': 'string'}}}
    result = check_template_compatibility('{{true}}', schema)
    assert result.is_compatible


def test_literal_false_in_mustache():
    """Schema checker should not crash on {{false}}."""
    schema = {'type': 'object', 'properties': {'x': {'type': 'string'}}, 'required': ['x']}
    result = check_template_compatibility('{{false}}', schema)
    assert result.is_compatible


def test_literal_null_in_mustache():
    """Schema checker should not crash on {{null}}."""
    schema = {'type': 'object', 'properties': {'x': {'type': 'string'}}, 'required': ['x']}
    result = check_template_compatibility('{{null}}', schema)
    assert result.is_compatible


def test_literal_number_in_mustache():
    """Schema checker should not crash on {{42}}."""
    schema = {'type': 'object', 'properties': {'x': {'type': 'string'}}, 'required': ['x']}
    result = check_template_compatibility('{{42}}', schema)
    assert result.is_compatible


def test_literal_string_in_mustache():
    """Schema checker should not crash on {{"hello"}}."""
    schema = {'type': 'object', 'properties': {'x': {'type': 'string'}}, 'required': ['x']}
    result = check_template_compatibility('{{"hello"}}', schema)
    assert result.is_compatible


def test_literal_undefined_in_mustache():
    """Schema checker should not crash on {{undefined}}."""
    schema = {'type': 'object', 'properties': {'x': {'type': 'string'}}, 'required': ['x']}
    result = check_template_compatibility('{{undefined}}', schema)
    assert result.is_compatible


# --- Schema: empty properties vs type object ---


def test_empty_properties_allows_any_field():
    """{'properties': {}} imposes no restriction on field access.

    An empty properties dict is falsy in Python, so the checker treats it as
    having no property constraints — any field access is allowed.
    """
    schema: dict[str, Any] = {'properties': {}}
    result = check_template_compatibility('{{anything}}', schema)
    assert result.is_compatible


def test_type_object_errors_for_field_access():
    """{'type': 'object'} with no properties errors for any {{field}} access.

    A schema with just type=object and no properties key means no fields are
    declared, so accessing any field is an error.
    """
    schema = {'type': 'object'}
    result = check_template_compatibility('{{field}}', schema)
    assert not result.is_compatible
    assert len(result.issues) == 1
    assert result.issues[0].field_path == 'field'


def test_properties_restricts_to_declared_fields():
    """{'properties': {'a': ...}} errors for fields not in properties.

    When properties is non-empty, only declared fields are accessible.
    """
    schema = {'properties': {'a': {'type': 'string'}}}
    result = check_template_compatibility('{{a}}', schema)
    assert result.is_compatible

    result = check_template_compatibility('{{b}}', schema)
    assert not result.is_compatible
    assert result.issues[0].field_path == 'b'


# --- Extra helpers not known by default ---


def test_extra_helper_not_known_by_default():
    """Extra helpers (json, eq, default, etc.) should NOT be treated as known
    helpers unless explicitly passed via the helpers parameter.

    Regression test: the schema checker previously used get_default_helpers()
    which included all 22 helpers, but the default environment only registers
    the 6 standard helpers.
    """
    schema = {
        'type': 'object',
        'properties': {'name': {'type': 'string'}},
        'required': ['name'],
    }
    # 'json' is an extra helper — not known by default
    result = check_template_compatibility('{{json name}}', schema)
    # Without helpers={'json'}, 'json' is treated as a field lookup, not a helper.
    # Since 'json' is not in the schema, this should fail.
    assert not result.is_compatible

    # Explicitly passing it makes it known
    result = check_template_compatibility('{{json name}}', schema, helpers={'json'})
    assert result.is_compatible


def test_extra_helpers_known_when_passed_explicitly():
    """Extra helpers work correctly when passed via the helpers parameter."""
    schema = {
        'type': 'object',
        'properties': {'val': {'type': 'string'}},
        'required': ['val'],
    }
    for helper_name in ('json', 'uppercase', 'lowercase', 'trim', 'eq', 'default'):
        result = check_template_compatibility(f'{{{{{helper_name} val}}}}', schema, helpers={helper_name})
        assert result.is_compatible, f'{helper_name} should be recognized when passed explicitly'


def test_standard_helpers_always_known():
    """Standard helpers (if, each, with, unless, lookup, log) are always known."""
    schema = {
        'type': 'object',
        'properties': {'items': {'type': 'array', 'items': {'type': 'string'}}},
        'required': ['items'],
    }
    # lookup and log are standard helpers — always known without passing helpers=
    result = check_template_compatibility('{{lookup items 0}}', schema)
    assert result.is_compatible
    result = check_template_compatibility('{{log items}}', schema)
    assert result.is_compatible


# --- Hash argument value validation ---


def test_hash_arg_literal_value():
    """Hash args with literal values should not cause issues."""
    schema = {
        'type': 'object',
        'properties': {'name': {'type': 'string'}},
        'required': ['name'],
    }
    result = check_template_compatibility('{{log name prefix="DEBUG:"}}', schema)
    assert result.is_compatible


def test_hash_arg_valid_field_reference():
    """Hash args with valid field path references should pass."""
    schema = {
        'type': 'object',
        'properties': {'name': {'type': 'string'}, 'style': {'type': 'string'}},
        'required': ['name', 'style'],
    }
    result = check_template_compatibility('{{log name format=style}}', schema)
    assert result.is_compatible


def test_hash_arg_invalid_field_reference():
    """Hash args with invalid field path references should be caught."""
    schema = {
        'type': 'object',
        'properties': {'name': {'type': 'string'}},
        'required': ['name'],
    }
    result = check_template_compatibility('{{log name format=missingField}}', schema)
    assert not result.is_compatible
    assert len(result.issues) == 1
    assert result.issues[0].field_path == 'missingField'


def test_hash_arg_block_helper():
    """Hash args on block helpers should also be validated."""
    schema = {
        'type': 'object',
        'properties': {'items': {'type': 'array', 'items': {'type': 'string'}}},
        'required': ['items'],
    }
    result = check_template_compatibility(
        '{{#myHelper items sort=missingField}}{{this}}{{/myHelper}}', schema, helpers={'myHelper'}
    )
    assert not result.is_compatible


def test_hash_arg_subexpression():
    """Hash args in subexpressions should be validated."""
    schema = {
        'type': 'object',
        'properties': {'name': {'type': 'string'}},
        'required': ['name'],
    }
    result = check_template_compatibility('{{(log name format=missingField)}}', schema)
    assert not result.is_compatible


def test_numeric_index_on_array_schema():
    schema = {
        'type': 'object',
        'properties': {
            'items': {
                'type': 'array',
                'items': {'type': 'string'},
            },
        },
        'required': ['items'],
    }
    result = check_template_compatibility('{{items.0}}', schema)
    assert result.is_compatible
    assert result.issues == []


def test_numeric_index_nested_array_schema():
    schema = {
        'type': 'object',
        'properties': {
            'data': {
                'type': 'object',
                'properties': {
                    'users': {
                        'type': 'array',
                        'items': {
                            'type': 'object',
                            'properties': {'name': {'type': 'string'}},
                            'required': ['name'],
                        },
                    },
                },
                'required': ['users'],
            },
        },
        'required': ['data'],
    }
    result = check_template_compatibility('{{data.users.0.name}}', schema)
    assert result.is_compatible
    assert result.issues == []


def test_numeric_index_array_without_items_schema():
    schema = {
        'type': 'object',
        'properties': {
            'items': {
                'type': 'array',
                'items': True,
            },
        },
        'required': ['items'],
    }
    result = check_template_compatibility('{{items.0}}', schema)
    assert result.is_compatible


def test_numeric_index_invalid_field_after():
    schema = {
        'type': 'object',
        'properties': {
            'items': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {'name': {'type': 'string'}},
                    'required': ['name'],
                },
            },
        },
        'required': ['items'],
    }
    result = check_template_compatibility('{{items.0.missing}}', schema)
    assert not result.is_compatible
    assert len(result.issues) == 1
    assert 'missing' in result.issues[0].message


def test_hash_arg_default_helper():
    """Hash args on the default helper should use relaxed severity."""
    schema = {
        'type': 'object',
        'properties': {'name': {'type': 'string'}},
        'required': ['name'],
    }
    # Hash arg referencing a field not in required — should use downgraded severity
    result = check_template_compatibility(
        '{{default name fallback=altName}}', schema, helpers={'default'}, optional_field_severity='ignore'
    )
    assert result.is_compatible
