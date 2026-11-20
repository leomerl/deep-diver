import logging
from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, col, select

from app.indexing.code_files import code_files
from app.models import DeepDive, DeepDiveCreate, Edge, EdgeKind, InterviewQuestion, Node, Repo
from app.workspace import Workspace

from .answer import DeepDiveAnswer
from .render_html import render_html
from .write_deep_dive import TASK_PROMPT

BREADCRUMB_SEPARATOR = " > "
NO_DESCRIPTION = "(none)"
WHOLE_REPO = ""  # a sparse path that checks out every file

type CloneArea = Callable[[str, str, list[str], Path, int | None], None]  # (url, sha, paths, dest, added_by)
type ListFiles = Callable[[Path], list[str]]
type Write = Callable[[int, Workspace, str, str], DeepDiveAnswer]  # (node_id, workspace, task, label) -> answer
type Forget = Callable[[int], None]  # drop the node's checkpoints once its row is committed
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
    """Check out the repo, write the deep dive about the node's paths, upload the HTML, save the row. A repeated job is a no-op."""
    # Delivery is at-least-once: a job can come back after a crash between commit and XACK.
    if session.exec(select(DeepDive.id).where(DeepDive.node_id == job.node_id)).first() is not None:
        forget(job.node_id)  # a redelivery after a commit whose forget never ran
        return
    node = session.get(Node, job.node_id)
    if node is None:
        logger.info("node %s is gone (its repo was removed); dropping the job", job.node_id)
        return
    repo = session.get(Repo, node.repo_id)
    if repo is None or repo.commit_sha is None:
        raise RuntimeError(f"node {job.node_id} belongs to a repo without a pinned commit")
    url, sha, paths, added_by = repo.url, repo.commit_sha, list(node.paths), repo.added_by
    label = BREADCRUMB_SEPARATOR.join((url.rsplit("/", 1)[-1], *_ancestors(session, node.id), node.name))
    task = TASK_PROMPT.format(
        repo=url, area=node.name, description=node.description or NO_DESCRIPTION, ancestors=label, scope=", ".join(paths)
    )
    session.rollback()  # end the read transaction: don't hold it open through a minutes-long agent run

    with TemporaryDirectory() as tmp:
        dest = Path(tmp) / "repo"
        # The whole repo, not just the node's paths: edge cases are often settled by callers and imports, and an
        # agent that can't read them guesses. It still writes about `paths` only (the task says so).
        clone(url, sha, [WHOLE_REPO], dest, added_by)
        # code_files drops secrets (.env, keys) and vendored files: what the agent reads ends up at the LLM provider.
        workspace = Workspace(root=dest, files=frozenset(code_files(list_files(dest))))
        answer = write(job.node_id, workspace, task, label)
        html = render_html(answer, workspace)  # needs the checkout for code excerpts
    # Upload before the insert: if the insert never happens, the retry re-uploads to the same key. The reverse
    # order could leave a row pointing at nothing.
    key = store(html)
    row = DeepDive(node_id=job.node_id, object_key=key).model_dump(exclude={"id"})  # fills created_at
    deep_dive_id = session.exec(
        insert(DeepDive)
        .values(**row)
        .on_conflict_do_nothing(index_elements=[col(DeepDive.node_id)])
        .returning(col(DeepDive.id))
    ).scalar_one_or_none()
    if deep_dive_id is None:
        session.rollback()  # a zombie worker finished first; its page and questions are as good as ours
        forget(job.node_id)
        return
    # Same transaction as the row: a deep dive is never visible without its questions.
    session.add_all(
        [InterviewQuestion(**q.model_dump(), deep_dive_id=deep_dive_id) for q in answer.interview_questions]
    )
    session.commit()
    forget(job.node_id)


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
