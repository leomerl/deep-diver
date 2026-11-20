from pathlib import PurePosixPath

from langchain_core.tools import BaseTool

from .make_tool import make_tool
from .manifest_names import MANIFEST_NAMES
from .output_limit import limit_lines
from .workspace import WHOLE_REPO, Workspace

LINES_PER_MANIFEST = 60  # the head of a manifest holds what matters: name, dependencies, entry points


def make_manifests_tool(workspace: Workspace) -> BaseTool:
    def manifests() -> str:
        """READMEs, dependency files, Dockerfiles and compose files in your scope (first 60 lines each), shallowest first."""
        found = sorted(
            (f for f in workspace.files_under(WHOLE_REPO) if PurePosixPath(f).name.lower() in MANIFEST_NAMES),
            key=lambda f: (f.count("/"), f),
        )
        if not found:
            return "no manifest files in your scope"
        return limit_lines([line for file in found for line in [f"=== {file}", *_head(workspace, file)]])

    return make_tool(manifests)


def _head(workspace: Workspace, file: str) -> list[str]:
    lines = workspace.file_path(file).read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[:LINES_PER_MANIFEST]
