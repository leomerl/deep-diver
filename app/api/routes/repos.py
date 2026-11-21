from subprocess import CalledProcessError, TimeoutExpired

from fastapi import APIRouter, HTTPException, status
from redis.exceptions import RedisError
from sqlmodel import Session, col, select

from app.auth import CurrentUser, git_env
from app.config import GIT_LS_REMOTE_TIMEOUT_S
from app.db import SessionDep
from app.git import ls_remote
from app.indexing import enqueue_index_job
from app.models import (
    Edge, EdgeRead, IndexJob, Node, NodeRead, Repo, RepoCreate, RepoMap, RepoRead, RepoStatus, Snapshot, SnapshotBase,
)

router = APIRouter(prefix="/repos", tags=["repos"])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def add_repo(repo: RepoCreate, user: CurrentUser, session: SessionDep) -> RepoCreate:
    """Idempotent per commit: a repo already queued at its HEAD isn't queued again. One indexed at an older commit
    is re-indexed."""
    job = IndexJob(url=repo.url, user_id=None if user is None else user.id)
    _enqueue(job, _head(session, job))
    return repo


@router.post("/{repo_id}/reindex", status_code=status.HTTP_202_ACCEPTED)
def reindex_repo(repo_id: int, user: CurrentUser, session: SessionDep) -> SnapshotBase:
    """Queue a snapshot of the repo's current HEAD; old snapshots and their deep dives stay. Answers with the commit
    the job will index; when that is already the current commit, nothing is queued."""
    row = session.exec(
        select(Repo, Snapshot.commit_sha)
        .join(Snapshot, col(Repo.current_snapshot_id) == col(Snapshot.id))
        .where(Repo.id == repo_id)
    ).first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "repo not found or not indexed")
    repo, current = row
    # The clicker's token when logged in, else the adder's: deep dives already clone with the adder's.
    job = IndexJob(url=repo.url, user_id=repo.added_by if user is None else user.id)
    head = _head(session, job)
    # shortcut: a HEAD that went back to a commit queued before keeps its old dedup marker, so nothing is queued and
    # the pointer stays; the client gives up after its poll limit. Upgrade: re-point in the API when that snapshot exists.
    if head != current:
        _enqueue(job, head)
    return SnapshotBase(repo_id=repo_id, commit_sha=head)


def _head(session: Session, job: IndexJob) -> str:
    # A private or missing repo fails here with git's reason, instead of in the worker where only the DLQ sees it.
    # Logged in: the check (and later the worker) clones with the user's GitHub token.
    try:
        return ls_remote(job.url, GIT_LS_REMOTE_TIMEOUT_S, env=git_env(session, job.url, job.user_id))
    except CalledProcessError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, e.__notes__[0].splitlines()[-1]) from e  # the "fatal:" line
    except TimeoutExpired as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "repo did not answer in time") from e


def _enqueue(job: IndexJob, head: str) -> None:
    try:
        enqueue_index_job(job, head)
    except RedisError as e:
        # Nothing was written, so a retry is safe.
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "queue unavailable, retry") from e


@router.get("")
def list_repos(session: SessionDep) -> list[RepoRead]:
    rows = session.exec(
        select(Repo, Snapshot.commit_sha)
        .join(Snapshot, col(Repo.current_snapshot_id) == col(Snapshot.id))
        .where(Repo.status == RepoStatus.indexed)
        .order_by(col(Repo.id))
    ).all()
    return [RepoRead.model_validate(repo, update={"commit_sha": sha}) for repo, sha in rows]


@router.get("/{repo_id}/map")
def get_map(repo_id: int, session: SessionDep) -> RepoMap:
    """The current snapshot's areas and the edges between them; the client draws the tree from the `contains` edges."""
    repo = session.get(Repo, repo_id)
    if repo is None or repo.status != RepoStatus.indexed or repo.current_snapshot_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "repo not found")
    snapshot_id = repo.current_snapshot_id
    nodes = session.exec(select(Node).where(Node.snapshot_id == snapshot_id).order_by(col(Node.id))).all()
    edges = session.exec(
        select(Edge)
        .join(Node, col(Edge.source_id) == col(Node.id))
        .where(Node.snapshot_id == snapshot_id)
        .order_by(col(Edge.id))
    ).all()
    return RepoMap(
        nodes=[NodeRead.model_validate(node) for node in nodes],
        edges=[EdgeRead.model_validate(edge) for edge in edges],
    )
