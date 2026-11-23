from pathlib import Path

import pytest
from pydantic import ValidationError

from app.deep_dive.answer import MAX_CELL_LINES, MAX_CELLS, AnswerContext, NotebookAnswer
from app.kroki import DiagramLanguage
from app.workspace import Workspace


def no_diagrams(language: DiagramLanguage, source: str) -> str:
    raise AssertionError("a notebook renders no diagrams")


@pytest.fixture
def context(tmp_path: Path) -> AnswerContext:
    (tmp_path / "queue.py").write_text("x = 1\n")
    return AnswerContext(Workspace(root=tmp_path, files=frozenset({"queue.py"})), no_diagrams)


def _cell(code: str = "print(1)", **fields: object) -> dict[str, object]:
    return {"explanation": "A lease expires unless renewed.", "code": code, "mirrors": "queue.py"} | fields


def _validate(context: AnswerContext, *cells: dict[str, object]) -> NotebookAnswer:
    return NotebookAnswer.model_validate({"title": "Leases by hand", "cells": [*cells]}, context=context)


def test_valid_notebook_passes(context: AnswerContext) -> None:
    code = "import heapq\nfrom collections import deque\nimport sqlite3\nprint(deque([1]), heapq.nsmallest(1, [2]))"
    _validate(context, _cell(code), _cell(mirrors=None))


def test_top_level_await_passes(context: AnswerContext) -> None:
    # Pyodide runs cells with top-level await, so an asyncio demo needs no asyncio.run.
    _validate(context, _cell("import asyncio\nawait asyncio.sleep(0)"), _cell())


def test_syntax_error_is_rejected_with_its_line(context: AnswerContext) -> None:
    with pytest.raises(ValidationError, match="doesn't parse: .* on line 2"):
        _validate(context, _cell("x = 1\ndef f(:"), _cell())


def test_every_blocked_import_is_listed_in_one_error(context: AnswerContext) -> None:
    code = "import threading\nfrom subprocess import run\nimport os.path\nimport numpy\ndef f():\n    import js"
    with pytest.raises(ValidationError, match="can't run in the browser: js, numpy, subprocess, threading\\."):
        _validate(context, _cell(code), _cell())


def test_relative_import_is_rejected(context: AnswerContext) -> None:
    with pytest.raises(ValidationError, match=r"can't run in the browser: \.\.queue"):
        _validate(context, _cell("from ..queue import lease"), _cell())


def test_mirrors_a_file_not_in_the_checkout_is_rejected(context: AnswerContext) -> None:
    with pytest.raises(ValidationError, match="'gone.py' is not a file in your scope"):
        _validate(context, _cell(mirrors="gone.py"), _cell())


def test_too_long_cell_is_rejected(context: AnswerContext) -> None:
    with pytest.raises(ValidationError, match=f"split it or cut it to {MAX_CELL_LINES}"):
        _validate(context, _cell("pass\n" * (MAX_CELL_LINES + 1)), _cell())


def test_tells_in_an_explanation_are_rejected(context: AnswerContext) -> None:
    with pytest.raises(ValidationError, match="remove AI-writing tells"):
        _validate(context, _cell(explanation="This cell — the heart of it — renews."), _cell())


def test_tells_in_the_title_are_rejected(context: AnswerContext) -> None:
    with pytest.raises(ValidationError, match="remove AI-writing tells"):
        NotebookAnswer.model_validate({"title": "Leases \u2014 by hand", "cells": [_cell(), _cell()]}, context=context)


@pytest.mark.parametrize("count", [1, MAX_CELLS + 1])
def test_cell_count_outside_the_bounds_is_rejected(context: AnswerContext, count: int) -> None:
    with pytest.raises(ValidationError, match="cells"):
        _validate(context, *[_cell()] * count)
