"""Tests for Pydantic integration with typed template rendering."""

import pytest

pytest.importorskip('pydantic')

from pydantic import BaseModel

from pydantic_handlebars import (
    CompiledTypedTemplate,
    HandlebarsEnvironment,
    TemplateSchemaError,
    compile,
    typed_compiler,
)


class User(BaseModel):
    name: str
    age: int


class Address(BaseModel):
    city: str
    country: str


class UserWithAddress(BaseModel):
    name: str
    address: Address


class UserWithOptional(BaseModel):
    name: str
    email: str | None = None


# --- compile(source, tp) one-shot API ---


def test_compile_typed_valid():
    template = compile('Hello {{name}}, age {{age}}!', User)
    assert isinstance(template, CompiledTypedTemplate)


def test_compile_typed_invalid():
    with pytest.raises(TemplateSchemaError):
        compile('Hello {{missing}}!', User)


def test_compile_typed_render():
    template = compile('Hello {{name}}, age {{age}}!', User)
    result = template.render(User(name='Alice', age=30))
    assert result == 'Hello Alice, age 30!'


def test_compile_typed_validate_and_render():
    template = compile('Hello {{name}}!', User)
    result = template.validate_and_render({'name': 'Bob', 'age': 25})
    assert result == 'Hello Bob!'


def test_compile_typed_validate_invalid():
    template = compile('Hello {{name}}!', User)
    with pytest.raises(Exception):
        template.validate_and_render({'invalid': True})


def test_compile_typed_nested():
    template = compile('{{name}} lives in {{address.city}}', UserWithAddress)
    result = template.render(UserWithAddress(name='Alice', address=Address(city='NYC', country='US')))
    assert result == 'Alice lives in NYC'


def test_compile_typed_optional():
    template = compile('{{name}} - {{email}}', UserWithOptional)
    result = template.render(UserWithOptional(name='Alice', email='alice@example.com'))
    assert result == 'Alice - alice@example.com'


# --- typed_compiler(tp) cached API ---


def test_typed_compiler_basic():
    compiler = typed_compiler(User)
    template = compiler.compile('Hello {{name}}, age {{age}}!')
    result = template.render(User(name='Alice', age=30))
    assert result == 'Hello Alice, age 30!'


def test_typed_compiler_json_schema():
    compiler = typed_compiler(User)
    schema = compiler.json_schema
    assert 'properties' in schema
    assert 'name' in schema['properties']
    assert 'age' in schema['properties']


def test_typed_compiler_no_raise():
    compiler = typed_compiler(User)
    template = compiler.compile('Hello {{missing}}!', raise_on_error=False)
    assert isinstance(template, CompiledTypedTemplate)


def test_typed_compiler_with_env():
    env = HandlebarsEnvironment()

    @env.helper
    def shout(*args: object, **kwargs: object) -> str:
        return str(args[0]).upper() + '!!!'

    _ = shout  # used via decorator registration
    compiler = typed_compiler(User, env=env)
    template = compiler.compile('{{shout name}}')
    result = template.render(User(name='Alice', age=30))
    assert result == 'ALICE!!!'


def test_typed_compiler_multiple_templates():
    compiler = typed_compiler(User)
    greeting = compiler.compile('Hello {{name}}!')
    info = compiler.compile('{{name}} is {{age}}.')
    user = User(name='Alice', age=30)
    assert greeting.render(user) == 'Hello Alice!'
    assert info.render(user) == 'Alice is 30.'
