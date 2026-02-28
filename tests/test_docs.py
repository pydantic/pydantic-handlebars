"""Test documentation code examples with pytest-examples."""

# pyright: reportUnknownMemberType=false

import pytest
from pytest_examples import CodeExample, EvalExample, find_examples


def set_eval_config(eval_example: EvalExample) -> None:
    eval_example.set_config(
        line_length=120,
        quotes='single',
        isort=True,
        target_version='py310',
    )


@pytest.mark.parametrize('example', find_examples('docs/', 'README.md'), ids=str)
def test_docs_lint(example: CodeExample, eval_example: EvalExample) -> None:
    set_eval_config(eval_example)
    if eval_example.update_examples:
        eval_example.format(example)
    else:
        eval_example.lint_ruff(example)


@pytest.mark.parametrize('example', find_examples('docs/', 'README.md'), ids=str)
def test_docs_run(example: CodeExample, eval_example: EvalExample) -> None:
    set_eval_config(eval_example)
    if eval_example.update_examples:
        eval_example.run_print_update(example)
    else:
        eval_example.run_print_check(example)
