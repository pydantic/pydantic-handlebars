# Security

pydantic-handlebars is designed to safely render untrusted templates:

## No Code Evaluation

The Handlebars expression language cannot call arbitrary Python functions, import modules, or
execute code. Only explicitly registered helpers can be invoked from templates. There is no `eval`,
`exec`, or dynamic code generation.

## Data Serialization

All context data is serialized to JSON-safe types via `pydantic_core.to_jsonable_python` before
rendering. The template engine only ever sees dicts, lists, strings, numbers, bools, and None —
there are no dangerous Python objects to exploit, no dunder attributes to traverse, no methods to
call, and no properties with side effects.

This eliminates entire categories of attacks:

- **No object traversal** — `__class__.__mro__.__subclasses__` chains are impossible because
  Python objects are converted to their JSON representation before the template sees them.
- **No method calls** — Callables in context are not passed through; they are serialized like
  any other value.
- **No side effects** — Properties with side effects are evaluated once during serialization,
  not during template rendering.

```python
from datetime import datetime

from pydantic_handlebars import render

# datetime is serialized to an ISO format string
print(render('{{date}}', {'date': datetime(2024, 1, 15)}))
#> 2024-01-15T00:00:00
```

Types that `pydantic_core` cannot serialize (arbitrary classes, functions, etc.) will raise a
`HandlebarsRuntimeError` at render time, ensuring that only safe, serializable data reaches
the template engine.

## Nesting Depth Limits

A maximum nesting depth (default: 100 levels) prevents stack overflow from deeply nested
templates. When exceeded, a `HandlebarsRuntimeError` is raised.

```python
from pydantic_handlebars import HandlebarsRuntimeError, render

# Extremely deep nesting will raise an error
deeply_nested = '{{#each a}}' * 200 + '{{this}}' + '{{/each}}' * 200

try:
    render(deeply_nested, {'a': [1]})
except HandlebarsRuntimeError:
    pass
```

## Output Size Limits

An optional maximum output size (default: 10 MB) prevents memory exhaustion from malicious
templates that produce extremely large output (e.g., nested `#each` over large arrays).

## HTML Escaping

By default, HTML escaping is **disabled** (`auto_escape=False`) since this library is designed for
prompt generation and other non-HTML use cases. When `auto_escape=True` is enabled, all
`{{expression}}` output is HTML-escaped. Characters escaped:

| Character | Escaped As |
|-----------|-----------|
| `&` | `&amp;` |
| `<` | `&lt;` |
| `>` | `&gt;` |
| `"` | `&quot;` |
| `'` | `&#x27;` |
| `` ` `` | `&#x60;` |
| `=` | `&#x3D;` |

`{{{triple}}}` and `{{&ampersand}}` syntax always output unescaped content regardless of the
`auto_escape` setting.

!!! warning
    If you use this library to render **HTML that will be displayed in a browser**, you **must**
    enable `auto_escape=True` to prevent cross-site scripting (XSS) vulnerabilities.

## Recommendations

- **Register only trusted helpers.** Custom helpers execute as Python code. Only register helpers
  you control and trust.
- **Validate templates against schemas.** Use the typed compilation API or
  `check_template_compatibility` to catch field reference errors before rendering, especially when
  templates come from external sources.
- **Monitor output size.** The default 10 MB limit is generous. Reduce it for your use case
  if appropriate.
- **Enable HTML escaping for HTML output.** If rendering templates into HTML for browser display,
  create an environment with `auto_escape=True`. Only use triple-stache for content you trust.
