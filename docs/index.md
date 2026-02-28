# pydantic-handlebars

Pure Python implementation of the [Handlebars](https://handlebarsjs.com/) template language with Pydantic-powered template validation.

Given a Handlebars template and a type (Pydantic model, dataclass, TypedDict, or anything with a JSON schema), validates when the template is compiled that it only references fields that exist in the schema — catching typos, missing fields, and structural mismatches before any data is rendered.

The Handlebars engine is pure Python with **zero runtime dependencies**. Install the optional `pydantic` extra for template-schema validation.

## Installation

```bash
pip install pydantic-handlebars
```

For template-schema validation (requires Pydantic 2.0+):

```bash
pip install pydantic-handlebars[pydantic]
```

Or with uv:

```bash
uv add pydantic-handlebars
```

Requires Python 3.10+. Pydantic 2.0+ is needed for typed template features.

## Quick Start

Render a template with a context dictionary:

```python
from pydantic_handlebars import render

print(render('Hello {{name}}!', {'name': 'World'}))
#> Hello World!
```

For repeated rendering, compile the template once and reuse it:

```python
from pydantic_handlebars import compile

template = compile('Hello {{name}}!')
print(template.render({'name': 'Alice'}))
#> Hello Alice!
print(template.render({'name': 'Bob'}))
#> Hello Bob!
```

## Type-Safe Templates

The core feature of this library: validate that a template is compatible with a data type *before* rendering.

```python
from pydantic import BaseModel

from pydantic_handlebars import compile


class User(BaseModel):
    name: str
    age: int


# Validates template fields against User's schema
template = compile('Hello {{name}}, age {{age}}!', User)

# Render with typed data — serialization handled automatically
print(template.render(User(name='Alice', age=30)))
#> Hello Alice, age 30!
```

If the template references a field that doesn't exist in the schema, compilation fails with a `TemplateSchemaError`. See [API Reference](api.md) for details.

## Custom Helpers

Use `HandlebarsEnvironment` to register custom helper functions:

```python
from pydantic_handlebars import HandlebarsEnvironment, HelperOptions

env = HandlebarsEnvironment()


@env.helper
def shout(*args: object, options: HelperOptions) -> str:
    return str(args[0]).upper() + '!!!'


print(env.render('{{shout name}}', {'name': 'world'}))
#> WORLD!!!
```

You can also register with a custom name:

```python
from pydantic_handlebars import HandlebarsEnvironment, HelperOptions

env = HandlebarsEnvironment()


@env.helper('loud')
def make_loud(*args: object, options: HelperOptions) -> str:
    return str(args[0]).upper()


print(env.render('{{loud name}}', {'name': 'world'}))
#> WORLD
```

## HTML Escaping

By default, `{{expression}}` HTML-escapes output. Use triple-stache `{{{expression}}}` or `{{&expression}}` for unescaped output:

```python
from pydantic_handlebars import SafeString, render

# Escaped by default
print(render('{{html}}', {'html': '<b>bold</b>'}))
#> &lt;b&gt;bold&lt;/b&gt;

# Triple-stache for unescaped
print(render('{{{html}}}', {'html': '<b>bold</b>'}))
#> <b>bold</b>

# SafeString marks content as pre-escaped
print(render('{{html}}', {'html': SafeString('<b>bold</b>')}))
#> <b>bold</b>
```

For non-HTML use cases like prompt generation, disable escaping entirely with `HandlebarsEnvironment(auto_escape=False)`.

## Error Handling

Parse and runtime errors include line and column information:

```python
from pydantic_handlebars import HandlebarsParseError, render

try:
    render('{{#if}}', {})
except HandlebarsParseError as e:
    assert e.line is not None
```

## What's Included

- Full Handlebars syntax: variables, paths, blocks, comments, literals, subexpressions
- All standard block helpers: `#if`, `#unless`, `#each`, `#with`, `lookup`, `log`
- Extra helpers (opt-in via `extra_helpers=True`): `json`, `uppercase`, `lowercase`, `trim`, `join`, `truncate`, `default`, comparison operators, boolean combinators
- Pydantic-powered template validation against JSON schemas
- Whitespace control with `~` markers
- `@data` variables: `@root`, `@index`, `@key`, `@first`, `@last`
- Block parameters: `{{#each items as |item index|}}`
- Chained else: `{{#if a}}...{{else if b}}...{{else}}...{{/if}}`
- Raw blocks: `{{{{raw}}}}...{{{{/raw}}}}`
- Security: dunder attribute access blocked, depth limits enforced

## What's Not Included

- Partials (`{{> partial}}`)
- Decorators
- Inline partials
- Strict mode
- Precompilation
