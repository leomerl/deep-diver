from langchain_core.tools import BaseTool

from .clusters_tool import make_clusters_tool
from .grep_tool import make_grep_tool
from .import_graph import ImportGraph
from .imports_tool import make_imports_tool
from .manifests_tool import make_manifests_tool
from .outline_tool import make_outline_tool
from .read_file_tool import make_read_file_tool
from .tree_tool import make_tree_tool
from .workspace import Workspace


def make_workspace_tools(workspace: Workspace, graph: ImportGraph) -> list[BaseTool]:
    """Every read-only tool, bound to one workspace. Big-picture tools first: the model reads the list in order."""
    return [
        make_tree_tool(workspace),
        make_manifests_tool(workspace),
        make_clusters_tool(workspace, graph),
        make_imports_tool(workspace, graph),
        make_outline_tool(workspace),
        make_grep_tool(workspace),
        make_read_file_tool(workspace),
    ]
