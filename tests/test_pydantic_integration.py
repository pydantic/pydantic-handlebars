"""Tests for Pydantic integration with typed template rendering."""

from datetime import datetime

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


class Event(BaseModel):
    title: str
    date: datetime


class Animal(BaseModel):
    name: str


class Dog(Animal):
    breed: str


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


# --- mode='json' serialization ---


def test_render_serializes_datetime_to_string():
    """render() uses mode='json', so datetime becomes an ISO string."""
    template = compile('Event: {{title}} on {{date}}', Event)
    event = Event(title='Launch', date=datetime(2024, 1, 15, 10, 30))
    result = template.render(event)
    assert '2024-01-15' in result
    assert 'Launch' in result


def test_validate_and_render_serializes_datetime_to_string():
    """validate_and_render() also uses mode='json', so datetime becomes an ISO string."""
    template = compile('Event: {{title}} on {{date}}', Event)
    result = template.validate_and_render({'title': 'Launch', 'date': '2024-01-15T10:30:00'})
    assert '2024-01-15' in result
    assert 'Launch' in result


# --- serialize_as_any ---


def test_serialize_as_any_default_strips_subclass_fields():
    """By default, subclass fields are stripped during serialization."""
    compiler = typed_compiler(Animal)
    template = compiler.compile('{{breed}}', raise_on_error=False)
    result = template.render(Dog(name='Rex', breed='Labrador'))
    assert result == ''


def test_serialize_as_any_via_compile():
    """compile() accepts serialize_as_any and threads it to the template."""
    template = compile('{{name}}', Animal, serialize_as_any=True)
    result = template.render(Dog(name='Rex', breed='Labrador'))
    assert result == 'Rex'


def test_serialize_as_any_via_typed_compiler():
    """serialize_as_any=True via typed_compiler() preserves subclass fields."""
    compiler = typed_compiler(Animal, serialize_as_any=True)
    template = compiler.compile('{{name}} ({{breed}})', raise_on_error=False)
    result = template.render(Dog(name='Rex', breed='Labrador'))
    assert result == 'Rex (Labrador)'


def test_serialize_as_any_validate_and_render():
    """serialize_as_any=True with validate_and_render preserves subclass fields."""
    compiler = typed_compiler(Animal, serialize_as_any=True)
    template = compiler.compile('{{name}} ({{breed}})', raise_on_error=False)
    result = template.validate_and_render(Dog(name='Rex', breed='Labrador'))
    assert result == 'Rex (Labrador)'
