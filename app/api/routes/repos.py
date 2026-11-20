from subprocess import CalledProcessError, TimeoutExpired

from fastapi import APIRouter, HTTPException, status
from redis.exceptions import RedisError
from sqlmodel import col, select

from app.auth import CurrentUser, git_env
from app.config import GIT_LS_REMOTE_TIMEOUT_S
from app.db import SessionDep
from app.git import ls_remote
from app.indexing import enqueue_index_job
from app.models import Edge, EdgeRead, IndexJob, Node, NodeRead, Repo, RepoCreate, RepoMap, RepoRead, RepoStatus

router = APIRouter(prefix="/repos", tags=["repos"])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def add_repo(repo: RepoCreate, user: CurrentUser, session: SessionDep) -> RepoCreate:
    """Idempotent: a repo that was already added is accepted again and not re-queued."""
    job = IndexJob(url=repo.url, user_id=None if user is None else user.id)
    # A private or missing repo fails here with git's reason, instead of in the worker where only the DLQ sees it.
    # Logged in: the check (and later the worker) clones with the user's GitHub token.
    try:
        ls_remote(repo.url, GIT_LS_REMOTE_TIMEOUT_S, env=git_env(session, repo.url, job.user_id))
    except CalledProcessError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, e.__notes__[0].splitlines()[-1]) from e  # the "fatal:" line
    except TimeoutExpired as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "repo did not answer in time") from e
    try:
        enqueue_index_job(job)
    except RedisError as e:
        # Nothing was written, so a retry is safe.
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "queue unavailable, retry") from e
    return repo


@router.get("")
def list_repos(session: SessionDep) -> list[RepoRead]:
    repos = session.exec(select(Repo).where(Repo.status == RepoStatus.indexed).order_by(col(Repo.id))).all()
    return [RepoRead.model_validate(repo) for repo in repos]


@router.get("/{repo_id}/map")
def get_map(repo_id: int, session: SessionDep) -> RepoMap:
    """Every area of the repo and the edges between them; the client draws the tree from the `contains` edges."""
    repo = session.get(Repo, repo_id)
    if repo is None or repo.status != RepoStatus.indexed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "repo not found")
    nodes = session.exec(select(Node).where(Node.repo_id == repo_id).order_by(col(Node.id))).all()
    edges = session.exec(
        select(Edge).join(Node, col(Edge.source_id) == col(Node.id)).where(Node.repo_id == repo_id).order_by(col(Edge.id))
    ).all()
    return RepoMap(
        nodes=[NodeRead.model_validate(node) for node in nodes],
        edges=[EdgeRead.model_validate(edge) for edge in edges],
    )
