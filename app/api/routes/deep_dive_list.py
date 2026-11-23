from fastapi import APIRouter, HTTPException, status
from fastapi.responses import HTMLResponse
from redis.exceptions import RedisError
from sqlmodel import col, select

from app.db import SessionDep
from app.deep_dive.enqueue_notebook import enqueue_notebook_job
from app.models import DeepDive, DeepDiveListItem, DeepDiveRead, Node, NotebookBase, NotebookJob, Repo, Snapshot

from .deep_dives import HtmlReaderDep, html_response

router = APIRouter(prefix="/deep-dives", tags=["deep dives"])


@router.get("")
def list_deep_dives(session: SessionDep) -> list[DeepDiveListItem]:
    """Every written deep dive, newest first, older snapshots' included."""
    # TODO [API:LOW] unpaginated; add a cursor on created_at once the list grows past a few hundred.
    rows = session.exec(
        select(DeepDive, Node.name, Repo.url, Repo.current_snapshot_id)
        .join(Snapshot, col(DeepDive.snapshot_id) == col(Snapshot.id))
        .join(Repo, col(Snapshot.repo_id) == col(Repo.id))
        .outerjoin(Node, col(DeepDive.node_id) == col(Node.id))  # outer: a root deep dive has no node
        .order_by(col(DeepDive.created_at).desc())
    ).all()
    return [
        DeepDiveListItem(
            **DeepDiveRead.model_validate(dive).model_dump(),
            node_name=name, repo_url=url, stale=dive.snapshot_id != current,
        )
        for dive, name, url, current in rows
    ]


@router.get("/{deep_dive_id}/html", response_class=HTMLResponse)
def get_deep_dive_page(deep_dive_id: int, session: SessionDep, read: HtmlReaderDep) -> HTMLResponse:
    """Any page by its own id. The node and repo routes only reach the current snapshot's root page."""
    row = session.get(DeepDive, deep_dive_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "deep dive not found")
    return html_response(row, read)


@router.get("/{deep_dive_id}/notebook")
def get_notebook(deep_dive_id: int, session: SessionDep, read: HtmlReaderDep) -> NotebookBase:
    """404 when the deep dive has no notebook: its agent failed, or the page predates notebooks."""
    row = session.get(DeepDive, deep_dive_id)
    if row is None or row.notebook_key is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no notebook for this deep dive")
    # Parsed, not passed through: the response is typed, and a bad object fails here instead of in the browser.
    return NotebookBase.model_validate_json(read(row.notebook_key))


@router.post("/{deep_dive_id}/notebook", status_code=status.HTTP_202_ACCEPTED)
def request_notebook(deep_dive_id: int, session: SessionDep) -> NotebookJob:
    """Queue the page's notebook. Idempotent: a page already queued isn't queued again, and a page that has a notebook
    makes the job a no-op. A dead-lettered job frees its marker, so this is how a failed notebook is retried."""
    if session.get(DeepDive, deep_dive_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "deep dive not found")
    try:
        enqueue_notebook_job(deep_dive_id)
    except RedisError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "queue unavailable, retry") from e
    return NotebookJob(deep_dive_id=deep_dive_id)
