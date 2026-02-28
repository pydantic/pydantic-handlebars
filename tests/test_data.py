"""Tests for @data variables.

Ported from handlebars.js spec/data.js.
"""

from pydantic_handlebars import render

# --- @root ---


def test_at_root():
    assert render('{{@root.name}}', {'name': 'Alice'}) == 'Alice'


def test_at_root_in_nested_context():
    template = '{{#each items}}{{{@root.prefix}}}{{this}} {{/each}}'
    assert render(template, {'items': ['a', 'b'], 'prefix': '>'}) == '>a >b '


# --- @index ---


def test_at_index_in_each():
    assert render('{{#each items}}{{@index}} {{/each}}', {'items': ['a', 'b', 'c']}) == '0 1 2 '


# --- @key ---


def test_at_key_in_each_object():
    assert render('{{#each obj}}{{@key}}:{{this}} {{/each}}', {'obj': {'a': '1', 'b': '2'}}) == 'a:1 b:2 '


# --- @first and @last ---


def test_at_first():
    template = '{{#each items}}{{#if @first}}FIRST{{else}}other{{/if}} {{/each}}'
    assert render(template, {'items': [1, 2, 3]}) == 'FIRST other other '


def test_at_last():
    template = '{{#each items}}{{#if @last}}LAST{{else}}other{{/if}} {{/each}}'
    assert render(template, {'items': [1, 2, 3]}) == 'other other LAST '


# --- Nested @data ---


def test_nested_each_data():
    template = '{{#each outer}}{{#each inner}}{{@../index}}.{{@index}} {{/each}}{{/each}}'
    data = {'outer': [{'inner': ['a', 'b']}, {'inner': ['c', 'd']}]}
    assert render(template, data) == '0.0 0.1 1.0 1.1 '


# --- @data with parent ---


def test_at_root_in_deeply_nested():
    template = '{{#each a}}{{#each b}}{{@root.val}}{{/each}}{{/each}}'
    data = {'a': [{'b': [1]}], 'val': 'root'}
    assert render(template, data) == 'root'
