import logging
from collections.abc import Callable

from sqlalchemy import update
from sqlmodel import Session, col

from app.models import DeepDive, NotebookBase, NotebookJob
from app.workspace import Workspace

from .answer import NotebookAnswer
from .checkout import CloneArea, ListFiles, checkout
from .deep_dive_task import deep_dive_task
from .page_text import page_text

type ReadPage = Callable[[str], str]  # object key -> html
type WriteNotebook = Callable[[Workspace, str, str, str], NotebookAnswer]  # (workspace, task, page text, label)
type StoreNotebook = Callable[[NotebookBase], str]  # notebook -> object key

logger = logging.getLogger(__name__)


def generate_notebook(
    session: Session,
    job: NotebookJob,
    clone: CloneArea,
    list_files: ListFiles,
    read_page: ReadPage,
    write: WriteNotebook,
    store: StoreNotebook,
) -> None:
    """Write a saved page's notebook: check out the page's commit, hand the agent the page's text, upload the
    notebook and point the row at it. A page that already has one is a no-op.

    Works from the page, not the agent's answer: the answer only exists while the deep dive job runs, and the page
    exists for every deep dive, those written before notebooks included. AgentFailed propagates: the job is retried
    with a fresh agent, then dead-lettered, and the page stays as it is.
    """
    row = session.get(DeepDive, job.deep_dive_id)
    if row is None:
        logger.info("deep dive %s is gone; dropping its notebook job", job.deep_dive_id)
        return
    if row.notebook_key is not None:  # a redelivery after the commit, or a page that got one meanwhile
        return
    target = deep_dive_task(session, row.snapshot_id, row.node_id)
    if target is None:
        logger.info("deep dive %s's target is gone; dropping its notebook job", job.deep_dive_id)
        return
    page = page_text(read_page(row.object_key))
    session.rollback()  # end the read transaction: don't hold it open through the agent run

    with checkout(clone, list_files, target.url, target.sha, target.added_by) as workspace:
        notebook = write(workspace, target.task, page, target.label)
    notebook_key = store(notebook)  # before the update, so the row never points at a missing object
    # `IS NULL`: a zombie worker that finished first keeps its notebook; both are valid.
    session.exec(
        update(DeepDive).where(col(DeepDive.id) == row.id, col(DeepDive.notebook_key).is_(None)).values(notebook_key=notebook_key)
    )
    session.commit()
