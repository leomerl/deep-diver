import ast
from typing import Self

from langchain_core.tools import ToolException
from pydantic import ValidationInfo, model_validator

from app.deep_dive.pyodide_modules import ALLOWED_MODULES
from app.models import NotebookCellBase

from .answer_context import AnswerContext
from .prose import check_prose

# The prompt asks for TARGET; the validator rejects past MAX. Models can't count lines, so a prompt that names the
# hard cap gets answers that land just over it (a 42-line cell against 40 cost a live notebook both its tries).
TARGET_CELL_LINES = 25  # one idea per cell, a step a reader can follow
MAX_CELL_LINES = 60  # past this it's a module pasted in
ALLOWED_HINT = "Use the standard library only, with asyncio instead of threads"


class NotebookCell(NotebookCellBase):
    """One step of the notebook: an explanation, then code that shows it. Cells run top to bottom in one interpreter."""

    @model_validator(mode="after")
    def _humanized(self) -> Self:
        check_prose(self.explanation)  # reuses the stored shape instead of redeclaring the field as `Prose`
        return self

    @model_validator(mode="after")
    def _runs_in_pyodide(self) -> Self:
        # Catches mistakes before the reader presses Run. Not a security boundary: `__import__("js")` gets past any
        # static check, so the browser runner's isolation is what contains the code.
        lines = len(self.code.splitlines())
        if lines > MAX_CELL_LINES:
            raise ValueError(f"the cell has {lines} lines; split it or cut it to {MAX_CELL_LINES}")
        try:
            tree = ast.parse(self.code)
        except SyntaxError as e:
            raise ValueError(f"the code doesn't parse: {e.msg} on line {e.lineno}") from e
        blocked = sorted(_imported_roots(tree) - ALLOWED_MODULES)
        if blocked:
            raise ValueError(f"imports that can't run in the browser: {', '.join(blocked)}. {ALLOWED_HINT}")
        return self

    @model_validator(mode="after")
    def _mirrors_a_real_file(self, info: ValidationInfo) -> Self:
        if self.mirrors is None:
            return self
        if not isinstance(info.context, AnswerContext):
            raise TypeError("NotebookCell is validated with an AnswerContext as context")
        try:
            info.context.workspace.file_path(self.mirrors)
        except ToolException as e:
            raise ValueError(str(e)) from e
        return self


def _imported_roots(tree: ast.Module) -> set[str]:
    """The top-level package of every import in the cell, nested ones included."""
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.partition(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            # A relative import keeps its dots, so it never matches: a cell is not a package and can't resolve it.
            module = node.module or ""
            roots.add("." * node.level + module if node.level else module.partition(".")[0])
    return roots
