from collections import Counter, defaultdict
from pathlib import PurePosixPath
from typing import Annotated

from langchain_core.tools import BaseTool
from pydantic import Field

from .make_tool import make_tool
from .output_limit import limit_lines
from .workspace import Workspace

TOP_KINDS = 3  # file types per folder line: enough to tell a Python package from a frontend folder
INDENT = "  "


def make_tree_tool(workspace: Workspace) -> BaseTool:
    def tree(
        path: Annotated[str, Field(description="Folder relative to the repo root; '.' means your whole scope.")] = ".",
        depth: Annotated[int, Field(description="How many folder levels below `path` to show.")] = 2,
    ) -> str:
        """Folders under a path with their file counts and main file types, plus the files directly in it. Start here."""
        base = workspace.normalize(path)
        files = workspace.files_under(path)
        folders: defaultdict[str, Counter[str]] = defaultdict(Counter)
        for file in files:
            dirs = _relative(file, base).split("/")[:-1]
            for level in range(1, min(max(depth, 1), len(dirs)) + 1):
                folders[_join(base, *dirs[:level])][_kind(file)] += 1
        direct = [file for file in files if "/" not in _relative(file, base)]
        return limit_lines([
            f"{base or '.'}/ ({_summary(Counter(map(_kind, files)))})",
            *(f"{INDENT * (1 + _relative(f, base).count('/'))}{f}/ ({_summary(c)})" for f, c in sorted(folders.items())),
            *(f"{INDENT}{file}" for file in direct),
        ])

    return make_tool(tree)


def _relative(path: str, base: str) -> str:
    return path.removeprefix(f"{base}/") if base else path


def _join(*parts: str) -> str:
    return "/".join(p for p in parts if p)


def _kind(file: str) -> str:
    name = PurePosixPath(file)
    return name.suffix or name.name  # "Dockerfile", "Makefile" have no suffix


def _summary(kinds: Counter[str]) -> str:
    top = ", ".join(f"{kind} {n}" for kind, n in kinds.most_common(TOP_KINDS))
    return f"{kinds.total()} files: {top}"
