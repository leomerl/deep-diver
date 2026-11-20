from sqlmodel import SQLModel

from .edge import EdgeRead
from .node import NodeRead


class RepoMap(SQLModel):
    """GET /repos/{id}/map: every area of the repo and the edges between them (the shape canvas libraries take)."""

    nodes: list[NodeRead]
    edges: list[EdgeRead]
