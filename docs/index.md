# pydantic-handlebars

A [Handlebars](https://handlebarsjs.com/) template engine for composing LLM prompts, built on Pydantic.

Designed for AI/agent developers who build system prompts from dynamic data — few-shot examples,
user-specific context, tool descriptions, and other content that shouldn't be hardcoded. Templates
are validated against Pydantic models at compile time, catching typos and missing fields before any
data is rendered.

The only runtime dependency is Pydantic (2.0+).

## Installation

```bash
pip install pydantic-handlebars
```

Or with uv:

```bash
uv add pydantic-handlebars
```

Requires Python 3.10+ and Pydantic 2.0+.

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

## Type-Safe Templates

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
`check_template_compatibility` — it returns a result object:

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

See [API Reference](api.md) for full details on typed compilation and schema checking.

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

By default, HTML escaping is **disabled** (`auto_escape=False`) since this library is designed for
prompt generation and other non-HTML use cases. To enable HTML escaping, create an environment with
`auto_escape=True`:

```python
from pydantic_handlebars import HandlebarsEnvironment, render

# No escaping by default
print(render('{{html}}', {'html': '<b>bold</b>'}))
#> <b>bold</b>

# Enable escaping for HTML use cases
env = HandlebarsEnvironment(auto_escape=True)
print(env.render('{{html}}', {'html': '<b>bold</b>'}))
#> &lt;b&gt;bold&lt;/b&gt;
```

!!! warning
    If you use this library to render **HTML that will be displayed in a browser**, you **must**
    enable `auto_escape=True` to prevent cross-site scripting (XSS) vulnerabilities.

Triple-stache `{{{expression}}}` and `{{&expression}}` always output unescaped content regardless
of the `auto_escape` setting.

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
- Security: context data serialized to JSON-safe types, depth limits enforced

## What's Not (Yet) Included

If any of these features would be useful to you, please
[open an issue](https://github.com/pydantic/pydantic-handlebars/issues) and let us know.

- Partials and inline partials (`{{> partial}}`, `{{#*inline}}`)
- Strict mode (error on missing variables instead of empty string)
- Decorators
- Precompilation
