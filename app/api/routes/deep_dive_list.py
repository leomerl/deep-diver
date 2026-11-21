from fastapi import APIRouter, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlmodel import col, select

from app.db import SessionDep
from app.models import DeepDive, DeepDiveListItem, DeepDiveRead, Node, Repo, Snapshot

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
