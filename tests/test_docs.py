"""Test documentation code examples with pytest-examples."""

# pyright: reportUnknownMemberType=false

import importlib.util
import sys

import pytest
from pytest_examples import CodeExample, EvalExample, find_examples

HAS_PYDANTIC = importlib.util.find_spec('pydantic') is not None

# Collect all examples once, and build a title -> source map for cross-referencing
_all_examples = list(find_examples('docs/', 'README.md'))
_titled_sources: dict[str, str] = {}
for _ex in _all_examples:
    _title = _ex.prefix_settings().get('title')
    if _title:
        _titled_sources[_title] = _ex.source


def set_eval_config(eval_example: EvalExample) -> None:
    eval_example.set_config(
        line_length=120,
        quotes='single',
        isort=True,
        target_version='py310',
    )


def _write_requires(example: CodeExample, eval_example: EvalExample) -> None:
    """Write required example files to tmp_path so imports resolve."""
    requires = example.prefix_settings().get('requires')
    if not requires:
        return
    for req in requires.split(','):
        req = req.strip()
        mod_name = req.removesuffix('.py')
        (eval_example.tmp_path / req).write_text(_titled_sources[req])
        sys.modules.pop(mod_name, None)
    sys.path.insert(0, str(eval_example.tmp_path))


@pytest.mark.parametrize('example', _all_examples, ids=str)
def test_docs_lint(example: CodeExample, eval_example: EvalExample) -> None:
    if not HAS_PYDANTIC and 'from pydantic import' in example.source:  # pragma: no cover
        pytest.skip('pydantic not installed')
    set_eval_config(eval_example)
    if eval_example.update_examples:  # pragma: no cover
        eval_example.format(example)
    else:
        eval_example.lint_ruff(example)


@pytest.mark.parametrize('example', _all_examples, ids=str)
def test_docs_run(example: CodeExample, eval_example: EvalExample) -> None:
    if not HAS_PYDANTIC and 'from pydantic import' in example.source:  # pragma: no cover
        pytest.skip('pydantic not installed')
    set_eval_config(eval_example)
    _write_requires(example, eval_example)
    if eval_example.update_examples:  # pragma: no cover
        eval_example.run_print_update(example)
    else:
        eval_example.run_print_check(example)
