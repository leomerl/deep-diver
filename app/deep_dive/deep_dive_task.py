from dataclasses import dataclass

from sqlmodel import Session, col, exists, select

from app.models import Edge, EdgeKind, Node, Repo, Snapshot

from .write_deep_dive import REPO_TASK_PROMPT, TASK_PROMPT

BREADCRUMB_SEPARATOR = " > "
NO_DESCRIPTION = "(none)"


@dataclass(frozen=True)
class DeepDiveTask:
    """What the agents need to know about a deep dive's target, and where to check it out."""

    url: str
    sha: str  # the snapshot's commit, not the repo's current one: the node's paths were checked against it
    added_by: int | None
    task: str  # the writer's task prompt; the notebook agent gets it too
    label: str  # `repo > area > node`, for logs and the agents' labels


def deep_dive_task(session: Session, snapshot_id: int, node_id: int | None) -> DeepDiveTask | None:
    """None when the target is gone (its repo was removed)."""
    snapshot = session.get(Snapshot, snapshot_id)
    repo = None if snapshot is None else session.get(Repo, snapshot.repo_id)
    node = None if node_id is None else session.get(Node, node_id)
    if snapshot is None or repo is None or (node_id is not None and node is None):
        return None
    repo_name = repo.url.rsplit("/", 1)[-1]
    if node is None:
        label = repo_name
        task = REPO_TASK_PROMPT.format(repo=repo.url, areas=_top_level_areas(session, snapshot_id))
    else:
        label = BREADCRUMB_SEPARATOR.join((repo_name, *_ancestors(session, node.id), node.name))
        task = TASK_PROMPT.format(
            repo=repo.url, area=node.name, description=node.description or NO_DESCRIPTION, ancestors=label,
            scope=", ".join(node.paths),
        )
    return DeepDiveTask(repo.url, snapshot.commit_sha, repo.added_by, task, label)


def _ancestors(session: Session, node_id: int | None) -> list[str]:
    """Names from the top-level area down to the node's parent."""
    names: list[str] = []
    while True:
        # Served by the partial unique index on edges.target_id for `contains`.
        parent = session.exec(
            select(Node)
            .join(Edge, col(Edge.source_id) == col(Node.id))
            .where(Edge.target_id == node_id, Edge.kind == EdgeKind.contains)
        ).first()
        if parent is None:
            return names[::-1]
        names.append(parent.name)
        node_id = parent.id


def _top_level_areas(session: Session, snapshot_id: int) -> str:
    """One line per area with no parent: the root deep dive's map of the system."""
    has_parent = exists().where(Edge.target_id == Node.id, Edge.kind == EdgeKind.contains)
    # Served by the index on nodes.snapshot_id, then the partial unique index on edges.target_id per node.
    nodes = session.exec(select(Node).where(Node.snapshot_id == snapshot_id, ~has_parent).order_by(col(Node.id))).all()
    return "\n".join(f"- {n.name} ({', '.join(n.paths)}): {n.description or NO_DESCRIPTION}" for n in nodes)
