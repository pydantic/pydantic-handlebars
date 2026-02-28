"""Tests for block helpers and inverted sections.

Ported from handlebars.js spec/blocks.js.
"""

# pyright: reportUnknownVariableType=false

from typing import Any

from pydantic_handlebars import HandlebarsEnvironment, HelperOptions, render


def test_array_iteration():
    template = '{{#each goodbyes}}{{text}}! {{/each}}cruel {{world}}!'
    data = {
        'goodbyes': [{'text': 'goodbye'}, {'text': 'Goodbye'}, {'text': 'GOODBYE'}],
        'world': 'world',
    }
    assert render(template, data) == 'goodbye! Goodbye! GOODBYE! cruel world!'


def test_array_with_index():
    template = '{{#each array}}{{@index}}: {{this}} {{/each}}'
    assert render(template, {'array': ['a', 'b', 'c']}) == '0: a 1: b 2: c '


def test_empty_block():
    template = '{{#each items}}item{{/each}}'
    assert render(template, {'items': []}) == ''


def test_block_with_else():
    template = '{{#each items}}item{{else}}no items{{/each}}'
    assert render(template, {'items': []}) == 'no items'


def test_inverted_section_with_caret():
    """Test {{^}} as inverse shorthand."""
    template = '{{#if show}}visible{{^}}hidden{{/if}}'
    assert render(template, {'show': True}) == 'visible'
    assert render(template, {'show': False}) == 'hidden'


def test_block_with_complex_lookup():
    template = '{{#each people}}{{../greeting}} {{name}}! {{/each}}'
    data = {'people': [{'name': 'Alan'}, {'name': 'Yehuda'}], 'greeting': 'Hello'}
    assert render(template, data) == 'Hello Alan! Hello Yehuda! '


def test_nested_blocks():
    template = '{{#each outer}}[{{#each inner}}({{this}}){{/each}}]{{/each}}'
    data = {'outer': [{'inner': [1, 2]}, {'inner': [3, 4]}]}
    assert render(template, data) == '[(1)(2)][(3)(4)]'


def test_block_helper_with_inverse():
    env = HandlebarsEnvironment()

    def list_helper(context: object, *args: Any, options: HelperOptions) -> str:
        items = args[0] if args else None
        if isinstance(items, list) and items:
            return '<ul>' + ''.join(f'<li>{options.fn(item)}</li>' for item in items) + '</ul>'
        return options.inverse(context)

    env.register_helper('list', list_helper)
    assert (
        env.render(
            '{{#list items}}{{name}}{{else}}empty{{/list}}',
            {
                'items': [{'name': 'a'}, {'name': 'b'}],
            },
        )
        == '<ul><li>a</li><li>b</li></ul>'
    )
    assert (
        env.render(
            '{{#list items}}{{name}}{{else}}empty{{/list}}',
            {
                'items': [],
            },
        )
        == 'empty'
    )


def test_standalone_inverted_section():
    """Test {{^}} used inside blocks."""
    template = '{{#each items}}{{this}}{{^}}nothing{{/each}}'
    assert render(template, {'items': [1, 2, 3]}) == '123'
    assert render(template, {'items': []}) == 'nothing'


def test_block_parent_scope():
    template = '{{#with person}}{{name}} from {{../city}}{{/with}}'
    data = {'person': {'name': 'Alice'}, 'city': 'NYC'}
    assert render(template, data) == 'Alice from NYC'


def test_deeply_nested_parent_scope():
    template = '{{#each a}}{{#each b}}{{../../name}}{{/each}}{{/each}}'
    data = {'a': [{'b': [1]}], 'name': 'root'}
    assert render(template, data) == 'root'
