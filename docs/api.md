# Python API Reference

## Module Functions

### `render`

Render a template string with a context dictionary:

```python
from pydantic_handlebars import render

print(render('Hello {{name}}!', {'name': 'World'}))
#> Hello World!
```

Uses a default environment with standard Handlebars helpers (`if`, `unless`, `each`, `with`,
`lookup`, `log`).

::: pydantic_handlebars.render

### `compile`

Compile a template into a reusable callable. When called with just a source string, returns a
`CompiledTemplate`. When called with a source string and a type, validates the template against the
type's JSON schema and returns a `CompiledTypedTemplate`:

```python
from pydantic_handlebars import compile

# Untyped compilation
template = compile('Hello {{name}}!')
print(template.render({'name': 'World'}))
#> Hello World!
```

```python
from pydantic import BaseModel

from pydantic_handlebars import compile


class User(BaseModel):
    name: str
    age: int


# Typed compilation — validates template against User's schema
template = compile('Hello {{name}}, age {{age}}!', User)
print(template.render(User(name='Alice', age=30)))
#> Hello Alice, age 30!
```

::: pydantic_handlebars.compile

### `typed_compiler`

Create a `TypedCompiler` for compiling multiple templates against the same type. Caches the type
adapter and JSON schema for efficiency:

```python
from pydantic import BaseModel

from pydantic_handlebars import typed_compiler


class User(BaseModel):
    name: str
    age: int


compiler = typed_compiler(User)

greeting = compiler.compile('Hello {{name}}!')
info = compiler.compile('{{name}} is {{age}} years old.')

user = User(name='Alice', age=30)
print(greeting.render(user))
#> Hello Alice!
print(info.render(user))
#> Alice is 30 years old.
```

::: pydantic_handlebars.typed_compiler

### `check_template_compatibility`

Validate a template (or list of templates) against a JSON schema without compiling:

```python
from pydantic_handlebars import check_template_compatibility

schema = {
    'type': 'object',
    'properties': {'name': {'type': 'string'}},
    'required': ['name'],
}

result = check_template_compatibility('Hello {{name}}!', schema)
print(result.is_compatible)
#> True

result = check_template_compatibility('{{missing_field}}', schema)
print(result.is_compatible)
#> False
print(result.issues[0].field_path)
#> missing_field
```

::: pydantic_handlebars.check_template_compatibility

## Classes

### `HandlebarsEnvironment`

An environment for rendering templates with custom helpers.

```python
from pydantic_handlebars import HandlebarsEnvironment, HelperOptions

env = HandlebarsEnvironment(extra_helpers=True)


@env.helper
def shout(*args: object, options: HelperOptions) -> str:
    return str(args[0]).upper() + '!!!'


print(env.render('{{shout name}}', {'name': 'world'}))
#> WORLD!!!
```

Pass `extra_helpers=True` to include additional utility, comparison, and boolean helpers beyond the
6 standard Handlebars.js helpers. See [Built-in Helpers](helpers.md) for the full list.

::: pydantic_handlebars.HandlebarsEnvironment

### `CompiledTemplate`

Returned by `compile(source)` (without a type). Call `.render()` with a context dict.

::: pydantic_handlebars.CompiledTemplate

### `CompiledTypedTemplate`

Returned by `compile(source, Type)`. Call `.render()` with an instance of the type, or
`.validate_and_render()` with unvalidated data:

```python
from pydantic import BaseModel

from pydantic_handlebars import compile


class User(BaseModel):
    name: str
    age: int


template = compile('Hello {{name}}!', User)

# .render() — expects a validated instance
print(template.render(User(name='Alice', age=30)))
#> Hello Alice!

# .validate_and_render() — validates input through Pydantic first
print(template.validate_and_render({'name': 'Bob', 'age': 25}))
#> Hello Bob!
```

::: pydantic_handlebars.CompiledTypedTemplate

### `TypedCompiler`

Returned by `typed_compiler()`. Caches the type adapter and JSON schema for compiling multiple
templates against the same type.

::: pydantic_handlebars.TypedCompiler

### `HelperOptions`

Passed to block helpers as the `options` keyword argument. Provides access to the block body,
inverse block, hash arguments, and data variables.

```python
from pydantic_handlebars import HandlebarsEnvironment, HelperOptions

env = HandlebarsEnvironment()


@env.helper('repeat')
def repeat_helper(*args: object, options: HelperOptions) -> str:
    times = int(options.hash.get('times', 1))
    return ''.join(options.fn() for _ in range(times))


print(env.render('{{#repeat times=3}}Ho {{/repeat}}', {}))
#> Ho Ho Ho
```

::: pydantic_handlebars.HelperOptions

### `SafeString`

Marks a string as already HTML-safe when returned from helpers. When `auto_escape=True`, helper
return values wrapped in `SafeString` bypass HTML escaping:

```python
from pydantic_handlebars import HandlebarsEnvironment, HelperOptions, SafeString

env = HandlebarsEnvironment(auto_escape=True)


@env.helper
def bold(*args: object, options: HelperOptions) -> SafeString:
    return SafeString(f'<b>{args[0]}</b>')


print(env.render('{{bold name}}', {'name': 'Alice'}))
#> <b>Alice</b>
```

!!! note
    `SafeString` values in context dicts are serialized to plain `str` before rendering, losing
    the safe marker. `SafeString` is primarily useful as a return type from helpers.

::: pydantic_handlebars.SafeString

### `CompatibilityResult`

Returned by `check_template_compatibility`. Contains `is_compatible` (bool) and `issues` (list of
`TemplateIssue`).

::: pydantic_handlebars.CompatibilityResult

### `TemplateIssue`

A single issue found during schema compatibility checking. Contains `field_path`, `message`, and
`severity`.

::: pydantic_handlebars.TemplateIssue

## Exceptions

### `HandlebarsError`

Base exception for all pydantic_handlebars errors.

::: pydantic_handlebars.HandlebarsError

### `HandlebarsParseError`

Raised when a template cannot be parsed. Includes `line` and `column` attributes:

```python
from pydantic_handlebars import HandlebarsParseError, render

try:
    render('{{{unclosed}', {})
except HandlebarsParseError as e:
    assert e.line is not None
    assert e.column is not None
```

::: pydantic_handlebars.HandlebarsParseError

### `HandlebarsRuntimeError`

Raised during template rendering (e.g., exceeding depth limits).

::: pydantic_handlebars.HandlebarsRuntimeError

### `TemplateSchemaError`

Raised by `compile(source, Type)` when the template references fields not present in the type's
JSON schema:

```python
from pydantic import BaseModel

from pydantic_handlebars import TemplateSchemaError, compile


class User(BaseModel):
    name: str


try:
    compile('{{missing}}', User)
except TemplateSchemaError as e:
    print(e)
    """
    1 error(s) found:
      - missing: Field 'missing' not found in schema
    """
```

::: pydantic_handlebars.TemplateSchemaError

## Utilities

### `escape_expression`

HTML-escape a string using Handlebars escaping rules:

```python
from pydantic_handlebars import escape_expression

print(escape_expression('<b>bold</b>'))
#> &lt;b&gt;bold&lt;/b&gt;
```

::: pydantic_handlebars.escape_expression
