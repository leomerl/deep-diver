from sqlmodel import Session

from app.models import Edge, EdgeKind, Node, TreeNode


def save_areas(session: Session, snapshot_id: int, areas: list[TreeNode]) -> None:
    """Insert the tree as nodes plus `contains` edges, one level at a time, in the caller's transaction."""
    level: list[tuple[TreeNode, int | None]] = [(area, None) for area in areas]
    while level:
        rows = [Node(**tree.model_dump(exclude={"children"}), snapshot_id=snapshot_id) for tree, _ in level]
        session.add_all(rows)
        session.flush()  # assigns ids: this level's edges and the next level need them
        session.add_all([
            Edge(source_id=parent_id, target_id=_id(row), kind=EdgeKind.contains)
            for (_, parent_id), row in zip(level, rows, strict=True)
            if parent_id is not None
        ])
        level = [(child, _id(row)) for (tree, _), row in zip(level, rows, strict=True) for child in tree.children]


def _id(row: Node) -> int:
    if row.id is None:
        raise RuntimeError("flush didn't assign a node id")
    return row.id
