from typing import Annotated

import networkx as nx
from langchain_core.tools import BaseTool
from pydantic import Field

from .import_graph import ImportGraph
from .make_tool import make_tool
from .output_limit import limit_lines
from .workspace import Workspace

LOUVAIN_SEED = 0  # community detection is randomized; a fixed seed makes the same repo give the same answer
MEMBERS_SHOWN = 12
MOST_IMPORTED_SHOWN = 10
INDENT = "  "


def make_clusters_tool(workspace: Workspace, graph: ImportGraph) -> BaseTool:
    def clusters(
        path: Annotated[str, Field(description="Folder relative to the repo root; '.' means your whole scope.")] = ".",
    ) -> str:
        """Groups of Python modules under a path that import each other a lot (community detection on the import
        graph), and the most imported modules. A strong hint for where area boundaries are."""
        inside = graph.modules_in(set(workspace.files_under(path)))
        links = nx.DiGraph((m, t) for m in inside for t in graph.imports.get(m, []) if t in inside and t != m)
        if links.number_of_edges() == 0:
            return "no imports between Python modules under this path"
        # Ties broken by name: grimp's module order varies between runs, and the same repo should read the same.
        undirected = nx.Graph()
        undirected.add_nodes_from(sorted(links.nodes))
        undirected.add_edges_from(sorted(links.to_undirected().edges))
        communities = sorted(
            nx.community.louvain_communities(undirected, seed=LOUVAIN_SEED), key=lambda c: (-len(c), min(c))
        )
        most_imported = sorted(links.in_degree(), key=lambda pair: (-pair[1], pair[0]))[:MOST_IMPORTED_SHOWN]
        return limit_lines([
            *(f"cluster {i} ({len(c)} modules): {_members(c)}" for i, c in enumerate(communities, 1)),
            "most imported:",
            *(f"{INDENT}{module} ({graph.modules[module]}): imported by {n}" for module, n in most_imported),
        ])

    return make_tool(clusters)


def _members(community: set[str]) -> str:
    shown = sorted(community)[:MEMBERS_SHOWN]
    more = len(community) - len(shown)
    return ", ".join(shown) + (f", ... {more} more" if more else "")
