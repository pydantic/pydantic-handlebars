# Security

pydantic-handlebars is designed to safely render untrusted templates:

## No Code Evaluation

The Handlebars expression language cannot call arbitrary Python functions, import modules, or
execute code. Only explicitly registered helpers can be invoked from templates. There is no `eval`,
`exec`, or dynamic code generation.

## Attribute Access Restrictions

All Python "dunder" attributes are blocked in template path lookups. Attempting to access
attributes like `__class__`, `__dict__`, `__globals__`, `__init__`, or any attribute starting
with `__` will return an empty string.

```python
from pydantic_handlebars import render

# These all render as empty string
print(render('{{obj.__class__}}', {'obj': object()}))
#> 
#>
print(render('{{obj.__dict__}}', {'obj': object()}))
#> 
#>
```

The `constructor` property is also blocked, matching Handlebars.js behavior.

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

By default, all `{{expression}}` output is HTML-escaped. This prevents XSS attacks when
rendering templates into HTML. Characters escaped:

| Character | Escaped As |
|-----------|-----------|
| `&` | `&amp;` |
| `<` | `&lt;` |
| `>` | `&gt;` |
| `"` | `&quot;` |
| `'` | `&#x27;` |
| `` ` `` | `&#x60;` |
| `=` | `&#x3D;` |

Use `{{{triple}}}` or `{{&ampersand}}` syntax to output unescaped content when needed.

## Recommendations

- **Use pre-serialized data.** Pass dicts, lists, and primitives to the renderer rather than
  arbitrary Python objects. Even with dunder blocking, exposing rich Python objects to the template
  context increases the surface area for unintended data access. The typed template API
  (`compile(source, Type)`) handles serialization automatically via Pydantic's `dump_python()`.
- **Register only trusted helpers.** Custom helpers execute as Python code. Only register helpers
  you control and trust.
- **Validate templates against schemas.** Use the typed compilation API or
  `check_template_compatibility` to catch field reference errors before rendering, especially when
  templates come from external sources.
- **Monitor output size.** The default 10 MB limit is generous. Reduce it for your use case
  if appropriate.
- **Use HTML escaping.** Keep the default escaping behavior. Only use triple-stache for
  content you trust.
