from .node import NodeRead


class NodeWithChildren(NodeRead):
    """GET /nodes/{id} response."""

    children: list[NodeRead]
