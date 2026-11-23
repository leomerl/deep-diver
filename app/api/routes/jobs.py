from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ValidationError
from redis.exceptions import RedisError
from sqlmodel import Session, col, select

from app.config import JOB_LEASE_S, rds
from app.db import SessionDep
from app.deep_dive import streams as deep_dive_streams
from app.deep_dive.graph import STEPS
from app.deep_dive.streams import (
    DEEP_DIVE_DEAD_STREAM, DEEP_DIVE_GROUP, DEEP_DIVE_STREAM, NOTEBOOK_DEAD_STREAM, NOTEBOOK_GROUP, NOTEBOOK_STREAM,
)
from app.indexing import streams as index_streams
from app.indexing.streams import INDEX_DEAD_STREAM, INDEX_GROUP, INDEX_STREAM
from app.jobs import follow_up_step, step_chain
from app.models import DeepDive, DeepDiveCreate, IndexJob, JobEvent, JobEventRead, JobRead, Node, NotebookJob, Repo, Snapshot
from app.queue import JobEventKind, StreamJob, stream_jobs

router = APIRouter(prefix="/jobs", tags=["jobs"])

LIMIT = 50  # newest jobs read per stream
MS_PER_S = 1000
NOTEBOOK_STEP = "notebook"  # the deep dive chain's last link: the notebook job it queues
UNKNOWN = "(unreadable or removed)"  # a bad payload, or a target deleted since
REMOVED_REPO = "(removed repo)"

type JobKey = tuple[str, str]  # (stream, entry id): entry ids are unique per stream only
type Target = tuple[int, int | None]  # (snapshot id, node id): a deep dive's target; no node = the whole repo


@router.get("")
def list_jobs(session: SessionDep) -> list[JobRead]:
    """The newest jobs of every queue, newest first. State comes from Redis, history from job_events."""
    lease_ms = int(JOB_LEASE_S * MS_PER_S)
    try:
        index = stream_jobs(rds, INDEX_STREAM, INDEX_GROUP, INDEX_DEAD_STREAM, lease_ms, LIMIT)
        dives = stream_jobs(rds, DEEP_DIVE_STREAM, DEEP_DIVE_GROUP, DEEP_DIVE_DEAD_STREAM, lease_ms, LIMIT)
        notebooks = stream_jobs(rds, NOTEBOOK_STREAM, NOTEBOOK_GROUP, NOTEBOOK_DEAD_STREAM, lease_ms, LIMIT)
    except RedisError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "queue unavailable, retry") from e
    events = _events(
        session,
        [(INDEX_STREAM, j.entry_id) for j in index]
        + [(DEEP_DIVE_STREAM, j.entry_id) for j in dives]
        + [(NOTEBOOK_STREAM, j.entry_id) for j in notebooks],
    )
    dive_targets = {j.entry_id: _deep_dive_target(j) for j in dives}
    notebook_targets = _notebook_targets(session, notebooks)
    labels = _target_labels(session, [*dive_targets.values(), *notebook_targets.values()])
    notebook_jobs = [_job(NOTEBOOK_STREAM, j, labels.get(notebook_targets[j.entry_id], UNKNOWN), events) for j in notebooks]
    # Newest first, so the first per target is its latest try (a request after a dead letter is a new job).
    latest_notebook: dict[Target, JobRead] = {}
    for job in notebook_jobs:
        target = notebook_targets[job.entry_id]
        if target is not None:
            latest_notebook.setdefault(target, job)

    def dive_job(job: StreamJob) -> JobRead:
        target = dive_targets[job.entry_id]
        notebook = None if target is None else latest_notebook.get(target)
        return _job(DEEP_DIVE_STREAM, job, labels.get(target, UNKNOWN), events, STEPS, (NOTEBOOK_STEP, notebook))

    dive_jobs = [dive_job(j) for j in dives]
    shown_as_follow_up = {d.follow_up.entry_id for d in dive_jobs if d.follow_up is not None}
    jobs = (
        [_job(INDEX_STREAM, j, _index_label(j), events) for j in index]
        + dive_jobs
        + [n for n in notebook_jobs if n.entry_id not in shown_as_follow_up]  # a page's own request, its deep dive gone from the list
    )
    return sorted(jobs, key=lambda j: j.queued_at, reverse=True)


def _job(
    stream: str,
    job: StreamJob,
    label: str,
    events: dict[JobKey, list[JobEventRead]],
    steps: Sequence[str] = (),
    follow_up: tuple[str, JobRead | None] | None = None,  # (step name, the job), for a job that queues another
) -> JobRead:
    history = events[(stream, job.entry_id)]
    started = [e.delivery for e in history if e.kind == JobEventKind.started]
    chain = step_chain(steps, history, job.state)
    if follow_up is not None:
        chain.append(follow_up_step(follow_up[0], follow_up[1], job.state))
    return JobRead(
        stream=stream,
        entry_id=job.entry_id,
        label=label,
        state=job.state,
        queued_at=datetime.fromtimestamp(int(job.entry_id.split("-")[0]) / MS_PER_S, UTC),
        # Redis drops the count on ack, so a finished job's tries come from its history.
        deliveries=job.deliveries if job.deliveries is not None else max(started, default=0),
        consumer=job.consumer,
        chain=chain,
        events=history,
        follow_up=None if follow_up is None else follow_up[1],
    )


def _events(session: Session, keys: list[JobKey]) -> defaultdict[JobKey, list[JobEventRead]]:
    by_job: defaultdict[JobKey, list[JobEventRead]] = defaultdict(list)
    if not keys:
        return by_job
    # A row-value IN, so Postgres can use ix_job_events_job on (stream, entry_id).
    rows = session.exec(
        select(JobEvent).where(sa.tuple_(col(JobEvent.stream), col(JobEvent.entry_id)).in_(keys)).order_by(col(JobEvent.id))
    ).all()
    for row in rows:
        by_job[(row.stream, row.entry_id)].append(JobEventRead.model_validate(row))
    return by_job


def _index_label(job: StreamJob) -> str:
    payload = _payload(IndexJob, job, index_streams.PAYLOAD_FIELD)
    return UNKNOWN if payload is None else payload.url


def _deep_dive_target(job: StreamJob) -> Target | None:
    payload = _payload(DeepDiveCreate, job, deep_dive_streams.PAYLOAD_FIELD)
    return None if payload is None else (payload.snapshot_id, payload.node_id)


def _notebook_targets(session: Session, jobs: list[StreamJob]) -> dict[str, Target | None]:
    """A notebook job names its page; the page names the target. None: unreadable, or the page is gone."""
    payloads = {j.entry_id: _payload(NotebookJob, j, deep_dive_streams.PAYLOAD_FIELD) for j in jobs}
    ids = {p.deep_dive_id for p in payloads.values() if p is not None}
    # Served by the primary key of deep_dives.
    rows = session.exec(select(DeepDive.id, DeepDive.snapshot_id, DeepDive.node_id).where(col(DeepDive.id).in_(ids))).all()
    targets = {deep_dive_id: (snapshot_id, node_id) for deep_dive_id, snapshot_id, node_id in rows}
    return {entry_id: None if p is None else targets.get(p.deep_dive_id) for entry_id, p in payloads.items()}


def _target_labels(session: Session, targets: list[Target | None]) -> dict[Target, str]:
    """`repo > node`, or `repo (whole repo)`, per target: two queries for the whole page."""
    valid = {t for t in targets if t is not None}
    # Served by the primary keys of nodes and snapshots.
    names = dict(session.exec(select(Node.id, Node.name).where(col(Node.id).in_({node for _, node in valid}))).all())
    urls = dict(
        session.exec(
            select(Snapshot.id, Repo.url)
            .join(Repo, col(Snapshot.repo_id) == col(Repo.id))
            .where(col(Snapshot.id).in_({snapshot for snapshot, _ in valid}))
        ).all()
    )

    def label(snapshot_id: int, node_id: int | None) -> str:
        repo = urls.get(snapshot_id, REMOVED_REPO).rsplit("/", 1)[-1]
        return f"{repo} (whole repo)" if node_id is None else f"{repo} > {names.get(node_id, f'node {node_id}')}"

    return {t: label(*t) for t in valid}


def _payload[T: BaseModel](model: type[T], job: StreamJob, field: str) -> T | None:
    """Queue payloads are untrusted input: one bad entry shows as unreadable instead of failing the page."""
    try:
        return model.model_validate_json(job.fields.get(field, ""))
    except ValidationError:
        return None
