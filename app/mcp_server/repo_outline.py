from collections import defaultdict
from collections.abc import Iterator, Mapping

from app.models import EdgeKind, NodeRead, RepoMap

INDENT = "  "
NO_PAGE = "no deep dive"


def repo_outline(repo_map: RepoMap, pages: Mapping[int | None, int]) -> str:
    """The tree as indented text, one area per line. An agent pays per token: `{nodes, edges}` JSON repeats every
    key and leaves the nesting to be joined from the edges. `pages` maps a node id to its deep dive's id; the None
    key is the whole-repo page."""
    children: defaultdict[int, list[int]] = defaultdict(list)
    for edge in repo_map.edges:
        if edge.kind == EdgeKind.contains:
            children[edge.source_id].append(edge.target_id)
    nodes = {node.id: node for node in repo_map.nodes}
    nested = {child for ids in children.values() for child in ids}

    def lines(node: NodeRead, depth: int) -> Iterator[str]:
        yield f"{INDENT * depth}- {node.name} (node {node.id}, {_page(pages, node.id)}) [{', '.join(node.paths)}]" + (
            f": {node.description}" if node.description else ""
        )
        # Recursion ends: `contains` edges form a tree (DESIGN §4).
        for child in children[node.id]:
            yield from lines(nodes[child], depth + 1)

    top_level = [node for node in repo_map.nodes if node.id not in nested]
    return "\n".join([f"whole repo ({_page(pages, None)})", *(line for node in top_level for line in lines(node, 0))])


def _page(pages: Mapping[int | None, int], node_id: int | None) -> str:
    return f"deep dive {pages[node_id]}" if node_id in pages else NO_PAGE
