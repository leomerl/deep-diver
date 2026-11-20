from fastapi import APIRouter, HTTPException, status
from sqlmodel import col, select

from app.db import SessionDep
from app.models import Edge, EdgeKind, Node, NodeRead, NodeWithChildren

router = APIRouter(prefix="/nodes", tags=["nodes"])


@router.get("/{node_id}")
def get_node(node_id: int, session: SessionDep) -> NodeWithChildren:
    node = session.get(Node, node_id)
    if node is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "node not found")
    children = session.exec(
        select(Node)
        .join(Edge, col(Edge.target_id) == col(Node.id))
        .where(Edge.source_id == node_id, Edge.kind == EdgeKind.contains)
        .order_by(col(Node.id))
    ).all()
    return NodeWithChildren.model_validate(
        node, update={"children": [NodeRead.model_validate(child) for child in children]}
    )
