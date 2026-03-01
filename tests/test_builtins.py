"""Tests for built-in block helpers.

Ported from handlebars.js spec/builtins.js.
"""

from pydantic_handlebars import render

# --- #if ---


class TestIf:
    pass


def test_if_truthy_string():
    assert (
        render('{{#if goodbye}}GOODBYE {{/if}}cruel {{world}}!', {'goodbye': True, 'world': 'world'})
        == 'GOODBYE cruel world!'
    )


def test_if_falsy():
    assert (
        render('{{#if goodbye}}GOODBYE {{/if}}cruel {{world}}!', {'goodbye': False, 'world': 'world'}) == 'cruel world!'
    )


def test_if_with_context_argument():
    assert (
        render('{{#if goodbye}}GOODBYE {{/if}}cruel {{world}}!', {'goodbye': 'bye', 'world': 'world'})
        == 'GOODBYE cruel world!'
    )


def test_if_with_empty_string():
    assert render('{{#if goodbye}}GOODBYE {{/if}}cruel {{world}}!', {'goodbye': '', 'world': 'world'}) == 'cruel world!'


def test_if_with_zero():
    assert render('{{#if goodbye}}GOODBYE {{/if}}cruel {{world}}!', {'goodbye': 0, 'world': 'world'}) == 'cruel world!'


def test_if_with_none():
    assert (
        render('{{#if goodbye}}GOODBYE {{/if}}cruel {{world}}!', {'goodbye': None, 'world': 'world'}) == 'cruel world!'
    )


def test_if_with_empty_list():
    assert render('{{#if goodbye}}GOODBYE {{/if}}cruel {{world}}!', {'goodbye': [], 'world': 'world'}) == 'cruel world!'


def test_if_with_nonempty_list():
    assert (
        render('{{#if goodbye}}GOODBYE {{/if}}cruel {{world}}!', {'goodbye': ['foo'], 'world': 'world'})
        == 'GOODBYE cruel world!'
    )


def test_if_else():
    assert (
        render('{{#if goodbye}}GOODBYE{{else}}Hello{{/if}} cruel {{world}}!', {'goodbye': False, 'world': 'world'})
        == 'Hello cruel world!'
    )


def test_if_else_truthy():
    assert (
        render('{{#if goodbye}}GOODBYE{{else}}Hello{{/if}} cruel {{world}}!', {'goodbye': True, 'world': 'world'})
        == 'GOODBYE cruel world!'
    )


def test_if_with_boolean_true():
    assert (
        render('{{#if goodbye}}GOODBYE {{/if}}cruel {{world}}!', {'goodbye': True, 'world': 'world'})
        == 'GOODBYE cruel world!'
    )


def test_if_with_boolean_false():
    assert (
        render('{{#if goodbye}}GOODBYE {{/if}}cruel {{world}}!', {'goodbye': False, 'world': 'world'}) == 'cruel world!'
    )


# --- #unless ---


def test_unless_truthy():
    assert (
        render('{{#unless goodbye}}HELLO {{/unless}}cruel {{world}}!', {'goodbye': True, 'world': 'world'})
        == 'cruel world!'
    )


def test_unless_falsy():
    assert (
        render('{{#unless goodbye}}HELLO {{/unless}}cruel {{world}}!', {'goodbye': False, 'world': 'world'})
        == 'HELLO cruel world!'
    )


def test_unless_with_else():
    assert render('{{#unless goodbye}}HELLO{{else}}GOODBYE{{/unless}}!', {'goodbye': True}) == 'GOODBYE!'


def test_unless_with_else_falsy():
    assert render('{{#unless goodbye}}HELLO{{else}}GOODBYE{{/unless}}!', {'goodbye': False}) == 'HELLO!'


# --- #each ---


def test_each_array():
    assert (
        render(
            '{{#each goodbyes}}{{text}}! {{/each}}cruel {{world}}!',
            {
                'goodbyes': [{'text': 'goodbye'}, {'text': 'Goodbye'}, {'text': 'GOODBYE'}],
                'world': 'world',
            },
        )
        == 'goodbye! Goodbye! GOODBYE! cruel world!'
    )


def test_each_with_index():
    assert render('{{#each items}}{{@index}}:{{this}} {{/each}}', {'items': ['a', 'b', 'c']}) == '0:a 1:b 2:c '


def test_each_with_first_last():
    assert (
        render(
            '{{#each items}}{{#if @first}}[{{/if}}{{this}}{{#if @last}}]{{/if}}{{/each}}',
            {
                'items': ['a', 'b', 'c'],
            },
        )
        == '[abc]'
    )


def test_each_object():
    assert render('{{#each obj}}{{@key}}:{{this}} {{/each}}', {'obj': {'a': '1', 'b': '2'}}) == 'a:1 b:2 '


def test_each_empty_array():
    assert render('{{#each items}}item{{else}}empty{{/each}}', {'items': []}) == 'empty'


def test_each_null():
    assert render('{{#each items}}item{{else}}empty{{/each}}', {'items': None}) == 'empty'


def test_each_nested():
    template = '{{#each outer}}{{#each inner}}{{this}}{{/each}}{{/each}}'
    data = {'outer': [{'inner': [1, 2]}, {'inner': [3, 4]}]}
    assert render(template, data) == '1234'


def test_each_with_block_params():
    assert (
        render('{{#each items as |item idx|}}{{idx}}:{{item}} {{/each}}', {'items': ['a', 'b', 'c']}) == '0:a 1:b 2:c '
    )


def test_each_object_with_block_params():
    assert render('{{#each obj as |val key|}}{{key}}={{val}} {{/each}}', {'obj': {'x': '1', 'y': '2'}}) == 'x=1 y=2 '


# --- #with ---


def test_with():
    assert render('{{#with person}}{{name}}{{/with}}', {'person': {'name': 'Alice'}}) == 'Alice'


def test_with_else():
    assert render('{{#with person}}{{name}}{{else}}nobody{{/with}}', {'person': None}) == 'nobody'


def test_with_else_truthy():
    assert render('{{#with person}}{{name}}{{else}}nobody{{/with}}', {'person': {'name': 'Alice'}}) == 'Alice'


def test_with_block_params():
    assert render('{{#with person as |p|}}{{p.name}}{{/with}}', {'person': {'name': 'Alice'}}) == 'Alice'


def test_with_nested_path():
    assert render('{{#with person}}{{address.city}}{{/with}}', {'person': {'address': {'city': 'NYC'}}}) == 'NYC'


# --- lookup ---


def test_lookup_basic():
    assert render('{{lookup obj "name"}}', {'obj': {'name': 'Alice'}}) == 'Alice'


def test_lookup_dynamic():
    assert render('{{lookup obj key}}', {'obj': {'name': 'Alice'}, 'key': 'name'}) == 'Alice'


def test_lookup_array():
    assert render('{{lookup arr 1}}', {'arr': ['a', 'b', 'c']}) == 'b'


def test_lookup_missing():
    assert render('{{lookup obj "missing"}}', {'obj': {'name': 'Alice'}}) == ''


def test_lookup_null_object():
    assert render('{{lookup obj "name"}}', {'obj': None}) == ''


# --- Chained else if ---


def test_chained_else_if():
    template = '{{#if a}}A{{else if b}}B{{else}}C{{/if}}'
    assert render(template, {'a': True, 'b': True}) == 'A'
    assert render(template, {'a': False, 'b': True}) == 'B'
    assert render(template, {'a': False, 'b': False}) == 'C'


def test_chained_else_if_multiple():
    template = '{{#if a}}A{{else if b}}B{{else if c}}C{{else}}D{{/if}}'
    assert render(template, {'a': False, 'b': False, 'c': True}) == 'C'
    assert render(template, {'a': False, 'b': False, 'c': False}) == 'D'


# --- Nested blocks ---


def test_nested_if():
    template = '{{#if outer}}{{#if inner}}both{{/if}}{{/if}}'
    assert render(template, {'outer': True, 'inner': True}) == 'both'
    assert render(template, {'outer': True, 'inner': False}) == ''
    assert render(template, {'outer': False, 'inner': True}) == ''


def test_if_inside_each():
    template = '{{#each items}}{{#if active}}{{name}} {{/if}}{{/each}}'
    data = {'items': [{'name': 'a', 'active': True}, {'name': 'b', 'active': False}, {'name': 'c', 'active': True}]}
    assert render(template, data) == 'a c '


def test_each_inside_if():
    template = '{{#if show}}{{#each items}}{{this}} {{/each}}{{/if}}'
    assert render(template, {'show': True, 'items': [1, 2, 3]}) == '1 2 3 '
    assert render(template, {'show': False, 'items': [1, 2, 3]}) == ''
