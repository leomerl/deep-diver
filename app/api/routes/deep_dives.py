from collections.abc import Callable
from functools import partial
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from redis.exceptions import RedisError
from sqlmodel import select

from app.config import DEEP_DIVE_BUCKET, s3
from app.db import SessionDep
from app.deep_dive.content_security_policy import HTML_CSP
from app.deep_dive.enqueue import enqueue_deep_dive_job
from app.deep_dive.read_html import read_html
from app.models import DeepDive, DeepDiveCreate, DeepDiveRead, Node

router = APIRouter(prefix="/nodes", tags=["deep dives"])


def get_html_reader() -> Callable[[str], str]:
    return partial(read_html, s3, DEEP_DIVE_BUCKET)


HtmlReaderDep = Annotated[Callable[[str], str], Depends(get_html_reader)]


@router.post("/{node_id}/deep-dive", status_code=status.HTTP_202_ACCEPTED)
def request_deep_dive(node_id: int, session: SessionDep) -> DeepDiveCreate:
    """Idempotent: a node that was already requested is accepted again and not re-queued."""
    if session.get(Node, node_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "node not found")
    job = DeepDiveCreate(node_id=node_id)
    try:
        enqueue_deep_dive_job(job)
    except RedisError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "queue unavailable, retry") from e
    return job


@router.get("/{node_id}/deep-dive")
def get_deep_dive(node_id: int, session: SessionDep) -> DeepDiveRead:
    """404 until the deep dive is written."""
    return DeepDiveRead.model_validate(_deep_dive(session, node_id))


@router.get("/{node_id}/deep-dive/html", response_class=HTMLResponse)
def get_deep_dive_html(node_id: int, session: SessionDep, read: HtmlReaderDep) -> HTMLResponse:
    # Proxied, so the bucket stays private.
    # TODO [API:LOW] at scale, redirect to a presigned URL so page bytes skip the API.
    html = read(_deep_dive(session, node_id).object_key)
    return HTMLResponse(html, headers={"Content-Security-Policy": HTML_CSP})


def _deep_dive(session: SessionDep, node_id: int) -> DeepDive:
    # Served by the unique constraint on deep_dives.node_id.
    row = session.exec(select(DeepDive).where(DeepDive.node_id == node_id)).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no deep dive for this node yet")
    return row
