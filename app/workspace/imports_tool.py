from collections import Counter
from typing import Annotated

from langchain_core.tools import BaseTool
from pydantic import Field

from .import_graph import ImportGraph
from .make_tool import make_tool
from .output_limit import limit_lines
from .workspace import Workspace

INDENT = "  "


def make_imports_tool(workspace: Workspace, graph: ImportGraph) -> BaseTool:
    def imports(
        path: Annotated[str, Field(description="Folder or Python file relative to the repo root.")],
    ) -> str:
        """For the Python code under a path: which outside modules it imports, and which outside modules import it.
        Shows how parts of the code depend on each other."""
        inside = graph.modules_in(set(workspace.files_under(path)))
        if not inside:
            return "no Python modules under this path (or no import graph for this repo)"
        outgoing = Counter(t for m in inside for t in graph.imports.get(m, []) if t not in inside)
        incoming = Counter(m for m, targets in graph.imports.items() if m not in inside for t in targets if t in inside)
        return limit_lines([
            f"{len(inside)} modules under {path}",
            "imports (module: how many imports point at it):", *_listed(outgoing, graph),
            "imported by:", *_listed(incoming, graph),
        ])

    return make_tool(imports)


def _listed(counts: Counter[str], graph: ImportGraph) -> list[str]:
    # Ties broken by name: grimp's module order varies between runs, and the same repo should read the same.
    ranked = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    return [f"{INDENT}{module} ({graph.modules[module]}): {n}" for module, n in ranked] or [f"{INDENT}none"]
