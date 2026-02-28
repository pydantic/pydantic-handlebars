# Syntax Reference

This page covers all supported Handlebars template syntax.

## Variable Interpolation

Use double curly braces to output a value:

```handlebars
{{name}}
```

Values are HTML-escaped by default. To output unescaped HTML, use triple-stache or `&`:

```handlebars
{{{rawHtml}}}
{{&rawHtml}}
```

## Paths

### Dot Notation

Access nested properties with dots:

```handlebars
{{person.name}}
{{article.author.name}}
```

### Slash Notation

Slashes work the same as dots:

```handlebars
{{person/name}}
```

### `this` Keyword

Refer to the current context:

```handlebars
{{this}}
{{this.name}}
{{./name}}
```

### Parent Scope

Access parent contexts with `../`:

```handlebars
{{#each items}}
  {{../title}} - {{name}}
{{/each}}
```

Multiple levels work too: `{{../../grandparent}}`.

### `@data` Variables

Special variables prefixed with `@`:

| Variable | Description |
|----------|-------------|
| `@root` | The root context |
| `@index` | Current array index (in `#each`) |
| `@key` | Current object key (in `#each`) |
| `@first` | `true` for the first iteration |
| `@last` | `true` for the last iteration |

```handlebars
{{#each items}}
  {{@index}}: {{this}}
{{/each}}
```

## Literals

Use literal values directly in expressions:

```handlebars
{{helper "string"}}
{{helper 'single quoted'}}
{{helper 42}}
{{helper 3.14}}
{{helper true}}
{{helper false}}
{{helper null}}
{{helper undefined}}
```

## Comments

Comments are stripped from output:

```handlebars
{{! This is a short comment }}
{{!-- This is a long comment
  that can span multiple lines --}}
```

## Whitespace Control

Add `~` to strip whitespace on that side of a tag:

```handlebars
{{~expression}}   {{!-- strips whitespace before --}}
{{expression~}}   {{!-- strips whitespace after --}}
{{~expression~}}  {{!-- strips both sides --}}
```

This works on all tag types including blocks:

```handlebars
{{~#each items~}}
  {{this}}
{{~/each~}}
```

## Block Helpers

Block helpers wrap a section of the template:

```handlebars
{{#if condition}}
  Rendered when truthy
{{/if}}
```

### Inverse / Else

Use `{{else}}` or `{{^}}` for the inverse block:

```handlebars
{{#if condition}}
  Truthy
{{else}}
  Falsy
{{/if}}

{{#if condition}}
  Truthy
{{^}}
  Falsy (same as else)
{{/if}}
```

### Chained Else

Chain conditions with `{{else if}}`:

```handlebars
{{#if a}}
  A is truthy
{{else if b}}
  B is truthy
{{else}}
  Neither
{{/if}}
```

### Block Parameters

Capture block values with `as |param|`:

```handlebars
{{#each items as |item index|}}
  {{index}}: {{item.name}}
{{/each}}

{{#with person as |p|}}
  {{p.name}}
{{/with}}
```

## Hash Arguments

Pass named arguments to helpers:

```handlebars
{{helper key="value" count=42}}
```

## Subexpressions

Nest helper calls as arguments using parentheses:

```handlebars
{{helper (subhelper arg)}}
{{#if (eq status "active")}}
  Active!
{{/if}}
```

## Raw Blocks

Raw blocks pass content through without processing:

```handlebars
{{{{raw}}}}
  {{this is not processed}}
{{{{/raw}}}}
```

The content between raw block tags is output as-is.

## Escaped Delimiters

To output literal `{{`, escape with a backslash:

```handlebars
\{{not a variable}}
```

This renders as `{{not a variable}}`.
