import logging
from collections.abc import Callable

from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, col, select

from app.models import DeepDive, DeepDiveCreate, InterviewQuestion
from app.queue import ReportStep
from app.workspace import Workspace

from .answer import DeepDiveAnswer
from .checkout import CloneArea, ListFiles, checkout
from .deep_dive_task import deep_dive_task
from .render_html import render_html

type Write = Callable[[str, Workspace, str, str, ReportStep], DeepDiveAnswer]  # (target key, workspace, task, label, …)
type Forget = Callable[[str], None]  # drop the target's checkpoints once its row is committed
type Store = Callable[[str], str]  # html -> object key
type EnqueueNotebook = Callable[[int], bool]  # deep dive id -> queued (False: already queued once)

logger = logging.getLogger(__name__)


def generate_deep_dive(
    session: Session,
    job: DeepDiveCreate,
    clone: CloneArea,
    list_files: ListFiles,
    write: Write,
    store: Store,
    forget: Forget,
    enqueue_notebook: EnqueueNotebook,
    report_step: ReportStep,
) -> None:
    """Check out the repo, write the deep dive about the node (or the whole repo), upload it, save the row, then queue
    its notebook job. A repeated job only re-queues the notebook (a no-op once queued)."""
    key = job.target_key
    # Delivery is at-least-once: a job can come back after a crash between commit and XACK. `node_id == None`
    # renders as IS NULL, so this one query is the node check and the root check.
    done = select(DeepDive.id).where(DeepDive.snapshot_id == job.snapshot_id, DeepDive.node_id == job.node_id)
    existing = session.exec(done).first()
    if existing is not None:
        forget(key)  # a redelivery after a commit whose forget or enqueue never ran
        enqueue_notebook(existing)
        return
    target = deep_dive_task(session, job.snapshot_id, job.node_id)
    if target is None:
        logger.info("%s is gone (its repo was removed); dropping the job", key)
        return
    session.rollback()  # end the read transaction: don't hold it open through a minutes-long agent run

    with checkout(clone, list_files, target.url, target.sha, target.added_by) as workspace:
        # It still writes about the node's paths only (the task says so), though it can read the whole repo.
        answer = write(key, workspace, target.task, target.label, report_step)
        html = render_html(answer, workspace)  # needs the checkout for code excerpts
    # Upload before the insert: if the insert never happens, the retry re-uploads to the same key. The reverse
    # order could leave a row pointing at nothing.
    object_key = store(html)
    row = DeepDive(**job.model_dump(), object_key=object_key).model_dump(exclude={"id"})
    deep_dive_id = session.exec(
        insert(DeepDive)
        .values(**row)
        .on_conflict_do_nothing()  # no target: covers both node_id's unique key and the root's partial one
        .returning(col(DeepDive.id))
    ).scalar_one_or_none()
    if deep_dive_id is None:
        session.rollback()  # a zombie worker finished first; its page, questions and notebook job are as good as ours
        forget(key)
        return
    # Same transaction as the row: a deep dive is never visible without its questions.
    session.add_all([InterviewQuestion(**q.model_dump(), deep_dive_id=deep_dive_id) for q in answer.interview_questions])
    session.commit()
    forget(key)
    # After the commit, so the notebook job always finds the row. If Redis is down this raises, the job is retried,
    # and the redelivery takes the `existing` branch above and queues it then.
    enqueue_notebook(deep_dive_id)
