from fastapi import APIRouter, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlmodel import col, select

from app.db import SessionDep
from app.models import DeepDive, DeepDiveCreate, DeepDiveRead, Repo

from .deep_dives import HtmlReaderDep, enqueue_or_503, html_response

router = APIRouter(prefix="/repos", tags=["deep dives"])


@router.post("/{repo_id}/deep-dive", status_code=status.HTTP_202_ACCEPTED)
def request_repo_deep_dive(repo_id: int, session: SessionDep) -> DeepDiveCreate:
    """The deep dive about the whole repo at its current snapshot. Idempotent, like the node one."""
    repo = session.get(Repo, repo_id)
    if repo is None or repo.current_snapshot_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "repo not found or not indexed")
    return enqueue_or_503(DeepDiveCreate(snapshot_id=repo.current_snapshot_id))


@router.get("/{repo_id}/deep-dive")
def get_repo_deep_dive(repo_id: int, session: SessionDep) -> DeepDiveRead:
    """The current snapshot's; 404 until it is written. Older snapshots' pages are under /deep-dives/{id}/html."""
    return DeepDiveRead.model_validate(_root_deep_dive(session, repo_id))


@router.get("/{repo_id}/deep-dive/html", response_class=HTMLResponse)
def get_repo_deep_dive_html(repo_id: int, session: SessionDep, read: HtmlReaderDep) -> HTMLResponse:
    return html_response(_root_deep_dive(session, repo_id), read)


def _root_deep_dive(session: SessionDep, repo_id: int) -> DeepDive:
    # Served by the repos primary key, then the partial unique index uq_deep_dives_snapshot_root.
    row = session.exec(
        select(DeepDive)
        .join(Repo, col(Repo.current_snapshot_id) == col(DeepDive.snapshot_id))
        .where(Repo.id == repo_id, col(DeepDive.node_id).is_(None))
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no deep dive for this repo yet")
    return row
