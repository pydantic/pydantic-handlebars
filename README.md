# pydantic-handlebars

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Handlebars template engine for composing LLM prompts, built on Pydantic.

Designed for AI/agent developers who build system prompts from dynamic data — few-shot examples,
user-specific context, tool descriptions, and other content that shouldn't be hardcoded. Templates
are validated against Pydantic models at compile time, catching typos and missing fields before any
data is rendered.

The only runtime dependency is Pydantic (2.0+).

## Installation

```bash
pip install pydantic-handlebars
```

Requires Python 3.10+ and Pydantic 2.0+.

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

## Prompt Composition

Templates are a natural fit for building LLM prompts from structured data. This example builds a
system prompt for a support agent — the guidelines and few-shot examples are data-driven, so they
can be stored in a database, customized per customer, and iterated on without code changes:

```python {title="agent_config.py"}
from pydantic import BaseModel

from pydantic_handlebars import compile


class Turn(BaseModel):
    role: str
    content: str


class AgentConfig(BaseModel):
    company: str
    guidelines: list[str]
    dos: list[Turn]
    donts: list[Turn]


system_prompt = compile(
    """\
You are a support agent for {{company}}.

{{#each guidelines~}}
- {{this}}
{{/each}}
Follow the patterns shown in these examples:

<examples label="good">
{{#each dos~}}
<{{role}}>
{{content}}
</{{role}}>
{{/each~}}
</examples>

<examples label="bad — avoid these patterns">
{{#each donts~}}
<{{role}}>
{{content}}
</{{role}}>
{{/each~}}
</examples>\
""",
    AgentConfig,
)

prompt = system_prompt.render(
    AgentConfig(
        company='Acme Corp',
        guidelines=[
            'Be concise and helpful',
            'Link to docs when relevant',
            "If unsure, escalate — don't guess",
        ],
        dos=[
            Turn(role='user', content='How do I reset my password?'),
            Turn(
                role='assistant',
                content='Go to Settings → Security → Reset Password. '
                "You'll get a confirmation email within 2 minutes.\n"
                'Docs: https://docs.acme.com/password-reset',
            ),
        ],
        donts=[
            Turn(role='user', content='How do I reset my password?'),
            Turn(
                role='assistant',
                content="I'm not sure, maybe check the settings page? "
                'Let me know if you find it!',
            ),
        ],
    )
)
print(prompt)
"""
You are a support agent for Acme Corp.

- Be concise and helpful
- Link to docs when relevant
- If unsure, escalate — don't guess

Follow the patterns shown in these examples:

<examples label="good">
<user>
How do I reset my password?
</user>
<assistant>
Go to Settings → Security → Reset Password. You'll get a confirmation email within 2 minutes.
Docs: https://docs.acme.com/password-reset
</assistant>
</examples>

<examples label="bad — avoid these patterns">
<user>
How do I reset my password?
</user>
<assistant>
I'm not sure, maybe check the settings page? Let me know if you find it!
</assistant>
</examples>
"""
```

The template references `company`, `guidelines`, `dos`, `donts`, `role`, and `content` — all
validated against `AgentConfig`'s schema at compile time. A typo like `{{guidlines}}` raises
`TemplateSchemaError` immediately:

```python {title="agent_config_error.py" requires="agent_config.py"}
from agent_config import AgentConfig

from pydantic_handlebars import TemplateSchemaError, compile

try:
    compile('Hello {{guidlines}}!', AgentConfig)  # typo!
except TemplateSchemaError as e:
    print(e)
    """
    1 error(s) found:
      - guidlines: Field 'guidlines' not found in schema
    """
```

For user-provided templates where you want to check for errors without raising, use
`check_template_compatibility` instead — it returns a result object with `is_compatible` and
`issues`:

```python {title="agent_config_check.py" requires="agent_config.py"}
from agent_config import AgentConfig
from pydantic import TypeAdapter

from pydantic_handlebars import check_template_compatibility

schema = TypeAdapter(AgentConfig).json_schema(mode='serialization')
result = check_template_compatibility('Hello {{guidlines}}!', schema)
print(result.is_compatible)
#> False
print(result.issues)
"""
[
    TemplateIssue(
        severity='error', message="Field 'guidlines' not found in schema", field_path='guidlines', template_index=0
    )
]
"""
```

## Type-Safe Templates

Templates can be validated against a data type at compile time, catching typos, missing fields, and
structural mismatches before any data is rendered.

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

### Subclass serialization

By default, typed templates only serialize the fields declared on the type you compile against — extra
fields from subclasses are stripped. This is the safer default since a subclass might add sensitive
fields (e.g. `password`). To include subclass fields, pass `serialize_as_any=True`:

```python
from pydantic import BaseModel

from pydantic_handlebars import typed_compiler


class Animal(BaseModel):
    name: str


class Dog(Animal):
    breed: str


# serialize_as_any=True: subclass fields are preserved
compiler = typed_compiler(Animal, serialize_as_any=True)
template = compiler.compile('{{name}} ({{breed}})', raise_on_error=False)
print(template.render(Dog(name='Rex', breed='Labrador')))
#> Rex (Labrador)
```

The same option is available on the `compile()` shortcut via
`compile(source, tp, serialize_as_any=True)`.

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

Because Handlebars is a widely adopted standard, LLMs are already familiar with its syntax — making it a natural choice when AI agents need to read, write, or modify templates.

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
whether a template is compatible with your data type. Template expressivity is in tension with static
analysis, and Handlebars strikes a good balance between the two.

### Industry adoption

Handlebars (or its Mustache subset) is widely used across the AI/agent ecosystem — in agent
frameworks, LLM observability platforms, prompt management tools, and API playgrounds. Its
familiarity and simplicity make it a common default when these tools need a template language for
prompt construction.

### JSON Schema as the validation medium

We use JSON Schema — rather than Python type reflection — as the validation medium. This makes the
checking portable: the same schema can validate templates regardless of what language the type was
originally defined in. A schema generated from a Rust struct, TypeScript interface, or Go struct
works identically. Pydantic models generate JSON schemas automatically via `model_json_schema()`, so
the integration is seamless.

All context data is automatically serialized to JSON-safe types before rendering — the template
engine only ever sees dicts, lists, strings, numbers, bools, and None. JSON Schema naturally
describes this serialized form. The typed template API (`compile(source, Type)`) handles
serialization via Pydantic's `dump_python(mode='json')`.

## Features

### Handlebars syntax

- Variables and paths: `{{name}}`, `{{person.name}}`, `{{../parent}}`
- Blocks: `{{#if}}`, `{{#unless}}`, `{{#each}}`, `{{#with}}`
- Comments: `{{! comment }}`, `{{!-- long comment --}}`
- Literals: strings, numbers, booleans, null
- Subexpressions: `{{helper (other arg)}}`
- Hash arguments: `{{helper key=value}}`
- Raw blocks: `{{{{raw}}}}...{{{{/raw}}}}`
- HTML escaping (opt-in): `{{escaped}}` vs `{{{unescaped}}}`
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

HTML escaping is **disabled by default** (`auto_escape=False`). This library is designed for prompt
generation and other non-HTML use cases where escaping `<`, `>`, `&`, etc. would corrupt the output.

> **Warning:** If you use this library to render **HTML that will be displayed in a browser**, you
> **must** enable `auto_escape=True` to prevent cross-site scripting (XSS) vulnerabilities.

To enable escaping, create an environment with `auto_escape=True`:

```python
from pydantic_handlebars import HandlebarsEnvironment

env = HandlebarsEnvironment(auto_escape=True)
print(env.render('{{content}}', {'content': '<b>bold</b>'}))
#> &lt;b&gt;bold&lt;/b&gt;
```

Triple-stache `{{{expression}}}` always outputs unescaped content regardless of the `auto_escape`
setting.

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

### Strict mode

Pass `strict=True` to fail loudly when a template references a path that does not exist on the
context, instead of silently rendering as the empty string:

```python
from pydantic_handlebars import HandlebarsRuntimeError, render

try:
    render('Hello {{name}}!', {}, strict=True)
except HandlebarsRuntimeError as e:
    print(e)
    #> Strict mode: 'name' references missing context key 'name'
```

Strict mode treats *missing* keys as errors but lets explicit `None` values through (so
`{'name': None}` still renders as `Hello !`). It applies to block-helper arguments
(`{{#if missing}}`) and `@data` variables (`{{@nope}}`) the same way it applies to direct lookups —
helper *names*, block params bound by `as |name|`, and `{{this}}` are unaffected.

Strict mode can also be set at the environment level: `HandlebarsEnvironment(strict=True)`.

### Static dependency extraction

`extract_dependencies` statically returns the set of top-level context fields a template depends
on — no rendering required:

```python
from pydantic_handlebars import extract_dependencies

extract_dependencies('Hello {{user_name}}!')
#> {'user_name'}

extract_dependencies('{{user.name}} <{{user.email}}>')
#> {'user'}

extract_dependencies('{{#each items}}{{name}}{{/each}}')
#> {'items'}

extract_dependencies('{{#each items}}{{../top}}{{/each}}')
#> {'items', 'top'}

extract_dependencies('{{#each items as |item|}}{{item.name}}{{/each}}')
#> {'items'}
```

The walker is scope-aware: `each` and `with` shift the context (their bodies' refs are not
top-level deps), `if`/`unless` do not, block params shadow context lookups locally, `../` walks the
scope chain back through opaque blocks, and `@root.foo` jumps to the root context directly.

Standard helpers (`if`, `unless`, `each`, `with`, `lookup`, `log`) are recognised by default; pass
`include_extra_helpers=True` or `helpers={...}` to extend the set.

### Configurable delimiters

`HandlebarsEnvironment`, `render`, `compile`, and `extract_dependencies` all accept `open_delim` and
`close_delim` parameters (defaulting to `{{` / `}}`). Custom delimiter pairs let you run a
rendering pass that consumes one set of placeholders without disturbing another set intended for a
later pass:

```python
from pydantic_handlebars import render

# Compose with @{...}@ — leaves the {{...}} placeholders for the next pass.
after_composition = render(
    'You are helping @{role}@. Greet {{user_name}}.',
    {'role': 'a designer'},
    open_delim='@{', close_delim='}@',
)
print(after_composition)
#> You are helping a designer. Greet {{user_name}}.

# Default pass picks up the remaining {{...}}.
print(render(after_composition, {'user_name': 'Alice'}))
#> You are helping a designer. Greet Alice.
```

All standard syntax works under custom delimiters: block helpers (`@{#if x}@…@{/if}@`),
whitespace control (`@{~x~}@`), comments (`@{! … }@`, `@{!-- … --}@`), escape sequences
(`\@{x}@` produces literal `@{x}@`), and the ampersand-unescape variant (`@{&x}@` opts out of
HTML escaping when `auto_escape=True`).

Triple-stache (`{{{...}}}`) and raw blocks (`{{{{...}}}}`) are only available with the default
delimiters — they have no unambiguous extension for arbitrary pairs. Use `@{&x}@` for the
per-expression escape opt-out, or set `auto_escape=False` on the environment.

The public delimiter parameters reject empty, identical, whitespace-edged, and expression-syntax-
conflicting (`"'()=|~`) pairs.

## Security

### Design principles

pydantic-handlebars is designed to safely render untrusted templates:

- **No code evaluation** — The Handlebars expression language cannot call arbitrary Python functions,
  import modules, or execute code. Only explicitly registered helpers can be invoked.
- **Data serialization** — All context data is serialized to JSON-safe types via
  `pydantic_core.to_jsonable_python` before rendering. The template engine only ever sees dicts,
  lists, strings, numbers, bools, and None — there are no dangerous Python objects to exploit, no
  dunders, no methods, no properties with side effects.
- **Depth limits** — Template nesting is capped (default 100 levels) to prevent stack overflow from
  recursive or deeply nested templates.
- **Output size limits** — Rendered output is capped (default 10MB) to prevent memory exhaustion
  from template expansion attacks.

### Recommendations

- **Register only trusted helpers** — Custom helpers execute as Python code. Only register helpers
  you control and trust.
- **Validate templates against schemas** — Use the typed compilation API or
  `check_template_compatibility` to catch field reference errors before rendering, especially when
  templates come from external sources.

## What's Not (Yet) Implemented

If any of these features would be useful to you, please
[open an issue](https://github.com/pydantic/pydantic-handlebars/issues) and let us know.

- **Partials** — `{{> partialName}}` for template composition. Out-of-line partials registered on
  the environment (schema-opaque at check time), and inline partials
  (`{{#*inline "name"}}...{{/inline}}`) that *are* schema-checked since their body is visible. An
  `allow_partials` flag to optionally disallow partial syntax.
- **Error messages with source context** — Show the relevant template snippet with a caret pointing
  to the problematic expression. Most of the infrastructure (token positions, source access) is
  already in place.
- **Non-primitive rendering detection** — Warning when `{{expression}}` would render a complex
  object (dict, nested model) rather than a primitive.
- **Conditional type checking** — Warning when `#if` is used on a field whose type is guaranteed
  truthy.

## License

MIT
