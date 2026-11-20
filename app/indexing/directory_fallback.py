from pathlib import PurePosixPath

from app.models import Grouping, TreeNode
from app.workspace import Workspace

WHOLE_SCOPE = "."
DESCRIPTION = "Folder {folder}, grouped by directory: the AI's areas for its parent failed validation twice."


def directory_fallback(workspace: Workspace) -> list[TreeNode]:
    """A node's children by folder: one per immediate subfolder of its scope. Files directly in it stay with it.

    Used only when the agent's answer for this node failed twice, so the tree is still validated, just plainer.
    """
    bases = workspace.scope or ("",)
    folders = sorted({
        folder
        for base in bases
        for file in workspace.files_under(WHOLE_SCOPE)
        if (folder := _child_folder(file, base))
    })
    return [
        TreeNode(
            name=PurePosixPath(folder).name,
            description=DESCRIPTION.format(folder=folder),
            paths=[folder],
            grouping=Grouping.fallback,
        )
        for folder in folders
    ]


def _child_folder(file: str, base: str) -> str | None:
    if base and not file.startswith(f"{base}/"):
        return None
    first, *rest = file.removeprefix(f"{base}/").split("/") if base else file.split("/")
    return "/".join(p for p in (base, first) if p) if rest else None
