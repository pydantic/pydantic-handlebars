# pydantic-handlebars

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

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

Requires Python 3.10+. Pydantic 2.0+ is needed for typed template features.

## Quick Start

```python
from pydantic_handlebars import render

# Simple variable interpolation
print(render('Hello {{name}}!', {'name': 'World'}))
#> Hello World!

# Dot-notation paths
print(render('{{person.name}}', {'person': {'name': 'Alice'}}))
#> Alice

# Block helpers
print(render('{{#each items}}{{this}}{{#unless @last}} {{/unless}}{{/each}}', {'items': ['a', 'b', 'c']}))
#> a b c

# Conditionals
print(render('{{#if show}}yes{{else}}no{{/if}}', {'show': True}))
#> yes
```

## Type-Safe Templates

The core feature of this library: validate that a template is compatible with a data type *before* rendering.

### Compile with a type

Pass a Pydantic model (or any type supported by
[`TypeAdapter`](https://docs.pydantic.dev/latest/api/type_adapter/)) as the second argument to
`compile`. The template is validated against the model's JSON schema at compile time:

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

If the template references a field that doesn't exist in the schema, compilation fails:

```python
from pydantic import BaseModel

from pydantic_handlebars import TemplateSchemaError, compile


class User(BaseModel):
    name: str
    age: int


try:
    compile('Hello {{username}}!', User)  # 'username' not in User
except TemplateSchemaError as e:
    print(e)
    """
    1 error(s) found:
      - username: Field 'username' not found in schema
    """
```

### TypedCompiler

When compiling multiple templates against the same type, `TypedCompiler` caches the type adapter and JSON schema:

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

### Data validation and rendering

Typed templates offer two rendering modes:

```python
from pydantic import BaseModel

from pydantic_handlebars import compile


class User(BaseModel):
    name: str
    age: int


template = compile('Hello {{name}}!', User)

# .render() — expects an already-validated instance of the type
print(template.render(User(name='Alice', age=30)))
#> Hello Alice!

# validate_and_render — validates input through Pydantic first,
# useful for unvalidated data (e.g., from a JSON API)
print(template.validate_and_render({'name': 'Bob', 'age': 25}))
#> Hello Bob!
```

### Schema checking API

For lower-level control, use `check_template_compatibility` directly with a JSON schema:

```python
from pydantic_handlebars import check_template_compatibility

schema = {
    'type': 'object',
    'properties': {
        'name': {'type': 'string'},
        'items': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {'label': {'type': 'string'}},
            },
        },
    },
    'required': ['name', 'items'],
}

# Valid template — all referenced fields exist
result = check_template_compatibility('{{name}}: {{#each items}}{{label}} {{/each}}', schema)
print(result.is_compatible)
#> True

# Invalid template — 'missing_field' not in schema
result = check_template_compatibility('{{missing_field}}', schema)
print(result.is_compatible)
#> False
print(result.issues[0].field_path)
#> missing_field
```

You can also check multiple templates at once, which is useful for systems that pair a system prompt with a user prompt template:

```python
from pydantic_handlebars import check_template_compatibility

schema = {
    'type': 'object',
    'properties': {'name': {'type': 'string'}},
    'required': ['name'],
}

result = check_template_compatibility(
    ['System: you are helping {{name}}', 'User said: {{name}} wants help'],
    schema,
)
print(result.is_compatible)
#> True
```

### What gets checked

The schema checker statically walks the template AST and validates:

- **Field existence** — `{{name}}` errors if `name` is not in the schema's `properties` (unless `additionalProperties` allows it)
- **Nested path walking** — `{{user.address.city}}` is validated through each level of the schema hierarchy
- **`#each` targets** — Verifies the target resolves to an array or object type; descends into the `items` schema for the loop body
- **`#with` targets** — Verifies the target resolves to an object and validates the body against it
- **`#if`/`#unless` conditions** — Validates the condition field exists in the schema
- **`@root` paths** — `{{@root.name}}` is validated against the root schema
- **`$ref` resolution** — Follows `$ref` pointers including Pydantic's `$defs`
- **Nullable types** — Unwraps `anyOf: [{...}, {type: 'null'}]` patterns from `Optional[X]`
- **Union types** — Checks field access across `anyOf`/`oneOf` variants
- **`default` helper** — `{{default field "fallback"}}` relaxes checking for its first argument, since the fallback guards against missing values
- **Custom helpers** — Arguments to registered helpers are validated; the helper body is treated as opaque (the checker can't know what context a custom helper provides)

## Why Handlebars?

In the age of agent development, templates are everywhere — system prompts, user-facing messages, tool descriptions. But templates have traditionally had a weakness: **no type checking**. A typo in a field name silently renders an empty string rather than failing loudly. This library captures more of the confidence you get from using Pydantic for data validation, applied to the template layer.

### Security

Jinja2 is the most popular Python template engine, but its own documentation for the
[sandbox](https://jinja.palletsprojects.com/en/stable/sandbox/) states: *"The sandbox alone is not a
solution for perfect security."* The sandbox docs further warn about error handling, resource
exhaustion, and data exposure risks. Jinja2 is also one of the most commonly exploited template
engines for
[Server-Side Template Injection (SSTI)](https://owasp.org/www-project-web-security-testing-guide/v42/4-Web_Application_Security_Testing/07-Input_Validation_Testing/18-Testing_for_Server-side_Template_Injection)
— because Jinja2 expressions can evaluate arbitrary Python, an attacker who controls template
content can achieve remote code execution.

Handlebars has **no code evaluation path by design**. There is no mechanism in the Handlebars syntax
to call arbitrary functions, access Python internals, or traverse object hierarchies beyond simple
property access. The attack surface for template injection does not exist at the language level.

### vs. PEP 750 template strings

Python 3.14 introduces [template strings (PEP 750)](https://peps.python.org/pep-0750/) — a new
`t"..."` prefix that captures interpolation structure instead of immediately evaluating. While useful
for developer-authored strings in source code, t-strings are **compile-time source-code literals**.
You cannot load a template from a database, accept one from user input, or read one from a
configuration file and use it as a t-string.

The PEP itself acknowledges this limitation: *"Projects such as Jinja are still needed in cases
where the template is less part of the software by the developers, and more part of customization by
designers or even content created by users."*

pydantic-handlebars is designed for exactly this case — dynamic templates from any source, validated
against a known schema.

### vs. Mustache and f-strings

**Mustache** is the logic-less subset of Handlebars. All Mustache templates are valid Handlebars.
However, Mustache lacks `#if`/`#else`, `#unless`, block parameters, and custom helpers — features
that are important for real-world prompt construction (conditional sections, iteration metadata,
domain-specific formatting).

**Python f-strings and `str.format()`** support only flat variable substitution — no dot-notation
paths, no loops, no conditionals, no custom logic. They also execute in the caller's scope, making
them unsuitable for untrusted templates.

### Static analyzability

Because the Handlebars grammar is constrained, templates can be parsed and analyzed without
execution. This is what makes the schema validation feature possible — you can know at compile time
whether a template is compatible with your data type. A more expressive template language would make
this static analysis intractable.

### Industry adoption

Handlebars (or its Mustache subset) has significant adoption in the AI/agent ecosystem:

- [**Microsoft Semantic Kernel**](https://learn.microsoft.com/en-us/semantic-kernel/concepts/prompts/handlebars-prompt-templates) uses Handlebars as its primary prompt template format. Their [architecture decision record](https://github.com/microsoft/semantic-kernel/blob/main/docs/decisions/0023-handlebars-template-engine.md) notes: *"the majority of LLMs already support the Handlebars interface when dealing with prompts, which helps improve the accuracy of the response."*
- [**Google Genkit / Dotprompt**](https://genkit.dev/docs/dotprompt/) extends Handlebars with GenAI-specific helpers for roles, media, and structured output.
- [**LangChain / LangSmith**](https://docs.langchain.com/langsmith/prompt-template-format) supports Mustache (the Handlebars subset) for advanced prompt templating.

### JSON Schema as the validation medium

We use JSON Schema — rather than Python type reflection — as the validation medium. This makes the
checking portable: the same schema can validate templates regardless of what language the type was
originally defined in. A schema generated from a Rust struct, TypeScript interface, or Go struct
works identically. Pydantic models generate JSON schemas automatically via `model_json_schema()`, so
the integration is seamless.

We recommend passing pre-serialized data (dicts, lists, primitives) to the rendering functions
rather than arbitrary Python objects. JSON Schema naturally describes this serialized form. The typed
template API (`compile(source, Type)`) handles serialization automatically via Pydantic's
`dump_python()`.

## Features

### Handlebars syntax

- Variables and paths: `{{name}}`, `{{person.name}}`, `{{../parent}}`
- Blocks: `{{#if}}`, `{{#unless}}`, `{{#each}}`, `{{#with}}`
- Comments: `{{! comment }}`, `{{!-- long comment --}}`
- Literals: strings, numbers, booleans, null
- Subexpressions: `{{helper (other arg)}}`
- Hash arguments: `{{helper key=value}}`
- Raw blocks: `{{{{raw}}}}...{{{{/raw}}}}`
- HTML escaping: `{{escaped}}` vs `{{{unescaped}}}`
- Whitespace control: `{{~expression~}}`
- `@data` variables: `@root`, `@index`, `@key`, `@first`, `@last`
- Block parameters: `{{#each items as |item index|}}`
- Chained else: `{{else if condition}}`

### Built-in helpers

| Category | Helpers | Availability |
|---|---|---|
| **Block** | `if`, `unless`, `each`, `with` | Standard |
| **Utility** | `lookup`, `log` | Standard |
| **String** | `json`, `uppercase`, `lowercase`, `trim`, `join`, `truncate`, `default` | Extra |
| **Comparison** | `eq`, `ne`, `gt`, `gte`, `lt`, `lte` | Extra |
| **Boolean** | `and`, `or`, `not` | Extra |

Standard helpers are always available. Extra helpers require `HandlebarsEnvironment(extra_helpers=True)`.

## Custom Helpers

Register helpers on a `HandlebarsEnvironment`:

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

To use custom helpers with typed templates, pass the environment to `typed_compiler`:

```python
from pydantic import BaseModel

from pydantic_handlebars import HandlebarsEnvironment, HelperOptions, typed_compiler

env = HandlebarsEnvironment()


@env.helper
def shout(*args: object, options: HelperOptions) -> str:
    return str(args[0]).upper() + '!!!'


class User(BaseModel):
    name: str


compiler = typed_compiler(User, env=env)
template = compiler.compile('{{shout name}}')
print(template.render(User(name='world')))
#> WORLD!!!
```

## Configuration

### HTML escaping

By default, `{{expression}}` output is HTML-escaped, matching Handlebars.js behavior. For non-HTML
use cases like prompt generation, disable escaping:

```python
from pydantic_handlebars import HandlebarsEnvironment

env = HandlebarsEnvironment(auto_escape=False)
print(env.render('{{content}}', {'content': '<b>bold</b>'}))
#> <b>bold</b>
```

Triple-stache `{{{expression}}}` always outputs unescaped content regardless of the `auto_escape`
setting.

> **Note:** The module-level `render()` and `compile()` functions use a default environment with
> `auto_escape=True`. To disable escaping, create a `HandlebarsEnvironment(auto_escape=False)` and
> use its `render()` method, or pass it to `typed_compiler()`.

### Unlisted field strictness

The `optional_field_severity` parameter controls how the schema checker handles references to fields
not explicitly listed in the schema's `properties`. By default, these are errors:

```python
from pydantic_handlebars import check_template_compatibility

schema = {
    'type': 'object',
    'properties': {'name': {'type': 'string'}},
    'required': ['name'],
}

# Default: unlisted fields are errors
result = check_template_compatibility('{{nickname}}', schema)
print(result.is_compatible)
#> False

# Lenient: unlisted fields are warnings (don't block compatibility)
result = check_template_compatibility('{{nickname}}', schema, optional_field_severity='warning')
print(result.is_compatible)
#> True
print(result.issues[0].severity)
#> warning
```

The `default` helper automatically relaxes this for its arguments, since the fallback value
guards against the field being missing:

```python
from pydantic_handlebars import check_template_compatibility

schema = {
    'type': 'object',
    'properties': {'name': {'type': 'string'}},
    'required': ['name'],
}

# 'nickname' is not in the schema, but default provides a fallback
result = check_template_compatibility(
    '{{default nickname "Anonymous"}}', schema, helpers={'default'}
)
print(result.is_compatible)
#> True
```

## Security

### Design principles

pydantic-handlebars is designed to safely render untrusted templates:

- **No code evaluation** — The Handlebars expression language cannot call arbitrary Python functions,
  import modules, or execute code. Only explicitly registered helpers can be invoked.
- **Dunder attribute blocking** — All `__dunder__` attribute access is blocked in path lookups,
  preventing traversal attacks via `__class__.__mro__.__subclasses__` and similar chains.
- **Depth limits** — Template nesting is capped (default 100 levels) to prevent stack overflow from
  recursive or deeply nested templates.
- **Output size limits** — Rendered output is capped (default 10MB) to prevent memory exhaustion
  from template expansion attacks.

### Recommendations

- **Use pre-serialized data** — Pass dicts, lists, and primitives to the renderer rather than
  arbitrary Python objects. Even with dunder blocking, exposing rich Python objects to the template
  context increases the surface area for unintended data access. The typed template API
  (`compile(source, Type)`) handles serialization automatically via Pydantic's `dump_python()`.
- **Register only trusted helpers** — Custom helpers execute as Python code. Only register helpers
  you control and trust.
- **Validate templates against schemas** — Use the typed compilation API or
  `check_template_compatibility` to catch field reference errors before rendering, especially when
  templates come from external sources.

## Future Directions

- **[Monty](https://github.com/pydantic/monty) integration** — Given the recommendation to operate
  on pre-serialized data, Monty (Pydantic's restricted Python runtime) could provide an additional
  sandboxed execution layer for template rendering.
- **Non-primitive rendering detection** — Warning when a `{{expression}}` would render a complex
  object type (e.g., a dict or nested model) rather than a string or primitive, which is usually a
  bug.
- **Conditional type checking** — Warning when `#if` is used on a field whose type is guaranteed to
  be truthy (e.g., a required object with properties), which likely indicates a logic error.

## License

MIT
