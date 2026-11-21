import logging
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, col, exists, select

from app.indexing.code_files import code_files
from app.models import DeepDive, DeepDiveCreate, Edge, EdgeKind, InterviewQuestion, Node, Repo, Snapshot
from app.workspace import Workspace

from .answer import DeepDiveAnswer
from .render_html import render_html
from .write_deep_dive import REPO_TASK_PROMPT, TASK_PROMPT

BREADCRUMB_SEPARATOR = " > "
NO_DESCRIPTION = "(none)"
WHOLE_REPO = ""  # a sparse path that checks out every file

type CloneArea = Callable[[str, str, list[str], Path, int | None], None]  # (url, sha, paths, dest, added_by)
type ListFiles = Callable[[Path], list[str]]
type Write = Callable[[str, Workspace, str, str], DeepDiveAnswer]  # (target key, workspace, task, label) -> answer
type Forget = Callable[[str], None]  # drop the target's checkpoints once its row is committed
type Store = Callable[[str], str]  # html -> object key

logger = logging.getLogger(__name__)


def generate_deep_dive(
    session: Session,
    job: DeepDiveCreate,
    clone: CloneArea,
    list_files: ListFiles,
    write: Write,
    store: Store,
    forget: Forget,
) -> None:
    """Check out the repo, write the deep dive about the node (or the whole repo), upload the HTML, save the row.
    A repeated job is a no-op."""
    key = job.target_key
    # Delivery is at-least-once: a job can come back after a crash between commit and XACK. `node_id == None`
    # renders as IS NULL, so this one query is the node check and the root check.
    done = select(DeepDive.id).where(DeepDive.snapshot_id == job.snapshot_id, DeepDive.node_id == job.node_id)
    if session.exec(done).first() is not None:
        forget(key)  # a redelivery after a commit whose forget never ran
        return
    snapshot = session.get(Snapshot, job.snapshot_id)
    repo = None if snapshot is None else session.get(Repo, snapshot.repo_id)
    node = None if job.node_id is None else session.get(Node, job.node_id)
    if snapshot is None or repo is None or (job.node_id is not None and node is None):
        logger.info("%s is gone (its repo was removed); dropping the job", key)
        return
    # The snapshot's commit, not the repo's current one: the node's paths were checked against this commit.
    url, sha, added_by = repo.url, snapshot.commit_sha, repo.added_by
    repo_name = url.rsplit("/", 1)[-1]
    if node is None:
        label = repo_name
        task = REPO_TASK_PROMPT.format(repo=url, areas=_top_level_areas(session, job.snapshot_id))
    else:
        label = BREADCRUMB_SEPARATOR.join((repo_name, *_ancestors(session, node.id), node.name))
        task = TASK_PROMPT.format(
            repo=url, area=node.name, description=node.description or NO_DESCRIPTION, ancestors=label,
            scope=", ".join(node.paths),
        )
    session.rollback()  # end the read transaction: don't hold it open through a minutes-long agent run

    with TemporaryDirectory() as tmp:
        dest = Path(tmp) / "repo"
        # The whole repo, not just the node's paths: edge cases are often settled by callers and imports, and an
        # agent that can't read them guesses. It still writes about `paths` only (the task says so).
        clone(url, sha, [WHOLE_REPO], dest, added_by)
        # code_files drops secrets (.env, keys) and vendored files: what the agent reads ends up at the LLM provider.
        workspace = Workspace(root=dest, files=frozenset(code_files(list_files(dest))))
        answer = write(key, workspace, task, label)
        html = render_html(answer, workspace)  # needs the checkout for code excerpts
    # Upload before the insert: if the insert never happens, the retry re-uploads to the same key. The reverse
    # order could leave a row pointing at nothing.
    object_key = store(html)
    row = DeepDive(**job.model_dump(), object_key=object_key).model_dump(exclude={"id"})  # fills created_at
    deep_dive_id = session.exec(
        insert(DeepDive)
        .values(**row)
        .on_conflict_do_nothing()  # no target: covers both node_id's unique key and the root's partial one
        .returning(col(DeepDive.id))
    ).scalar_one_or_none()
    if deep_dive_id is None:
        session.rollback()  # a zombie worker finished first; its page and questions are as good as ours
        forget(key)
        return
    # Same transaction as the row: a deep dive is never visible without its questions.
    session.add_all(
        [InterviewQuestion(**q.model_dump(), deep_dive_id=deep_dive_id) for q in answer.interview_questions]
    )
    session.commit()
    forget(key)


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
