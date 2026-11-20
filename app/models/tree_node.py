from sqlmodel import Field

from .node import NodeBase


class TreeNode(NodeBase):
    """Indexing output before it has ids: an area and its sub-areas. Saved as nodes plus `contains` edges."""

    children: list["TreeNode"] = Field(default_factory=list)
