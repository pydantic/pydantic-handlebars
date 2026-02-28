# Built-in Helpers

pydantic_handlebars includes all standard Handlebars.js helpers. Additional utility, comparison, and
boolean helpers are available as opt-in extras.

## Standard Helpers

These 6 helpers are always available — they're included in every `HandlebarsEnvironment` and in the
module-level `render()` function.

### `#if`

Conditionally renders the block if the value is truthy.

Falsy values: `false`, `None`, `""`, `0`, `[]`.
Note: empty dict `{}` is **truthy** (matching Handlebars.js behavior).

```handlebars
{{#if author}}
  <h1>{{firstName}} {{lastName}}</h1>
{{else}}
  <h1>Unknown Author</h1>
{{/if}}
```

```python
from pydantic_handlebars import render

print(render('{{#if show}}visible{{else}}hidden{{/if}}', {'show': True}))
#> visible
```

Supports chained conditions:

```handlebars
{{#if a}}A{{else if b}}B{{else}}C{{/if}}
```

### `#unless`

The inverse of `#if`. Renders the block when the value is falsy.

```handlebars
{{#unless license}}
  WARNING: No license specified!
{{/unless}}
```

### `#each`

Iterates over arrays and objects.

For arrays, provides `@index`, `@first`, and `@last`:

```handlebars
{{#each items}}
  {{@index}}: {{this}}
{{/each}}
```

For objects, also provides `@key`:

```handlebars
{{#each person}}
  {{@key}}: {{this}}
{{/each}}
```

Supports `{{else}}` for empty collections:

```handlebars
{{#each items}}
  {{this}}
{{else}}
  No items found.
{{/each}}
```

Block parameters capture the value and index/key:

```handlebars
{{#each items as |item i|}}
  {{i}}: {{item.name}}
{{/each}}
```

Access the parent context with `../`:

```handlebars
{{#each items}}
  {{../title}}: {{name}}
{{/each}}
```

### `#with`

Changes the context for the block body.

```handlebars
{{#with person}}
  {{name}} lives in {{city}}
{{/with}}
```

Supports `{{else}}` for falsy contexts:

```handlebars
{{#with author}}
  {{name}}
{{else}}
  Unknown author
{{/with}}
```

### `lookup`

Dynamic property lookup:

```handlebars
{{lookup object key}}
```

```python
from pydantic_handlebars import render

print(render('{{lookup colors 0}}', {'colors': ['red', 'green', 'blue']}))
#> red
print(render('{{lookup person field}}', {'person': {'name': 'Alice'}, 'field': 'name'}))
#> Alice
```

### `log`

Logs values using Python's `warnings.warn`:

```handlebars
{{log "debug info" level="warn"}}
```

## Extra Helpers

The helpers below are **not** part of the Handlebars.js spec. They must be explicitly enabled:

```python
from pydantic_handlebars import HandlebarsEnvironment

env = HandlebarsEnvironment(extra_helpers=True)
```

### Utility Helpers

#### `json`

Serialize a value to a JSON string:

```handlebars
{{json data}}
```

```python
from pydantic_handlebars import HandlebarsEnvironment

env = HandlebarsEnvironment(extra_helpers=True)
print(env.render('{{{json obj}}}', {'obj': {'a': 1}}))
#> {"a": 1}
```

#### `uppercase`

Convert a value to uppercase:

```handlebars
{{uppercase name}}
```

#### `lowercase`

Convert a value to lowercase:

```handlebars
{{lowercase name}}
```

#### `trim`

Strip leading and trailing whitespace:

```handlebars
{{trim value}}
```

#### `join`

Join array elements with a separator:

```handlebars
{{join items ", "}}
```

```python
from pydantic_handlebars import HandlebarsEnvironment

env = HandlebarsEnvironment(extra_helpers=True)
print(env.render('{{join colors ", "}}', {'colors': ['red', 'green', 'blue']}))
#> red, green, blue
```

The default separator is `,`.

#### `truncate`

Truncate a string to N characters:

```handlebars
{{truncate description 50}}
```

The default length is 100.

#### `default`

Use a fallback value when the primary value is falsy:

```handlebars
{{default name "Anonymous"}}
```

### Comparison Helpers

These return boolean values and are typically used inside `#if` via subexpressions.

#### `eq` / `ne`

Equality and inequality:

```handlebars
{{#if (eq status "active")}}Active{{/if}}
{{#if (ne count 0)}}Has items{{/if}}
```

#### `gt` / `gte` / `lt` / `lte`

Numeric comparisons:

```handlebars
{{#if (gt age 18)}}Adult{{/if}}
{{#if (lte score 100)}}Valid{{/if}}
```

### Boolean Helpers

#### `and` / `or` / `not`

Boolean combinators for use in subexpressions:

```handlebars
{{#if (and hasPermission isActive)}}
  Allowed
{{/if}}

{{#if (or isAdmin isModerator)}}
  Has access
{{/if}}

{{#if (not isDisabled)}}
  Enabled
{{/if}}
```

`and` and `or` accept multiple arguments:

```handlebars
{{#if (and a b c)}}All truthy{{/if}}
{{#if (or a b c)}}At least one truthy{{/if}}
```
