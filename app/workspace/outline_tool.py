from collections.abc import Iterator
from pathlib import PurePosixPath
from typing import Annotated

import griffe
from langchain_core.tools import BaseTool
from pydantic import Field

from .make_tool import make_tool
from .output_limit import limit_lines
from .workspace import Workspace

PYTHON_SUFFIX = ".py"
INDENT = "  "
PRIVATE_PREFIX = "_"  # private helpers are detail, not the big picture
VARIADIC_PREFIX = {griffe.ParameterKind.var_positional: "*", griffe.ParameterKind.var_keyword: "**"}


def make_outline_tool(workspace: Workspace) -> BaseTool:
    def outline(
        path: Annotated[str, Field(description="Python file or folder relative to the repo root.")],
    ) -> str:
        """Public classes and functions in Python files under a path: signatures and first docstring lines, no bodies."""
        files = [f for f in workspace.files_under(path) if f.endswith(PYTHON_SUFFIX)]
        if not files:
            return "no Python files under this path"
        return limit_lines([line for file in files for line in _outline_file(workspace, file)])

    return make_tool(outline)


def _outline_file(workspace: Workspace, file: str) -> list[str]:
    source = workspace.file_path(file)
    try:
        # visit() parses statically: the repo's code is never imported or run.
        module = griffe.visit(PurePosixPath(file).stem, filepath=source, code=source.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return [f"{file}: could not parse"]
    return [file, *_members(module, depth=1)]


def _members(parent: griffe.Object, depth: int) -> Iterator[str]:
    for name, member in parent.members.items():
        # Aliases are imports; they belong to the module they come from.
        if member.is_alias or name.startswith(PRIVATE_PREFIX):
            continue
        if isinstance(member, griffe.Class):
            yield f"{INDENT * depth}class {name}{_doc(member)}"
            yield from _members(member, depth + 1)
        elif isinstance(member, griffe.Function):
            yield f"{INDENT * depth}def {name}({_parameters(member)}){_returns(member)}{_doc(member)}"


def _parameters(function: griffe.Function) -> str:
    return ", ".join(
        VARIADIC_PREFIX.get(p.kind, "")
        + p.name
        + (f": {p.annotation}" if p.annotation else "")
        + (f" = {p.default}" if p.default is not None and p.kind not in VARIADIC_PREFIX else "")
        for p in function.parameters
    )


def _returns(function: griffe.Function) -> str:
    return f" -> {function.returns}" if function.returns else ""


def _doc(obj: griffe.Object) -> str:
    return f"  # {obj.docstring.value.splitlines()[0]}" if obj.docstring and obj.docstring.value else ""
