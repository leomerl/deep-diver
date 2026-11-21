from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import func, or_, update
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, col, select

from app.indexing.code_files import code_files
from app.indexing.save_areas import save_areas
from app.models import IndexJob, Repo, RepoStatus, Snapshot, TreeNode

Clone = Callable[[str, Path], str]  # (url, dest) -> commit SHA
ListFiles = Callable[[Path], list[str]]  # checkout dir -> tracked paths
Explore = Callable[[Path, list[str], str], list[TreeNode]]  # (checkout, code files, repo name) -> top-level areas


def index_repo(session: Session, job: IndexJob, clone: Clone, list_files: ListFiles, explore: Explore) -> None:
    """Clone HEAD, build its snapshot unless that commit has one, and make it the repo's current snapshot.

    Serves both the first index and a re-index. A repeated job finds its snapshot built and only re-points."""
    # Read on the DB clock before cloning: a later reading saw a HEAD at least as new. This is the pointer's fence.
    head_seen_at = session.exec(select(func.clock_timestamp())).one()
    sha, areas = _checkout_and_explore(session, job.url, clone, list_files, explore)
    repo_id = _upsert_repo(session, job)
    snapshot_id = _snapshot_id(session, job.url, sha) if areas is None else _insert_snapshot(session, repo_id, sha, areas)
    if snapshot_id is None:
        session.rollback()  # another worker committed this commit's tree first, and moved the pointer itself
        return
    _point(session, repo_id, snapshot_id, head_seen_at)
    # Snapshot, tree and pointer commit together: a repo never shows a missing or partial tree.
    session.commit()


def _checkout_and_explore(
    session: Session, url: str, clone: Clone, list_files: ListFiles, explore: Explore
) -> tuple[str, list[TreeNode] | None]:
    """The HEAD commit and its areas; None instead of areas when that commit is already built (no agents run)."""
    with TemporaryDirectory() as tmp:
        dest = Path(tmp) / "repo"
        sha = clone(url, dest)
        built = _snapshot_id(session, url, sha) is not None
        session.rollback()  # end the read transaction: don't hold it open through minutes of agents
        # The agents read the checkout through their tools, so it has to exist until exploring ends.
        return sha, None if built else explore(dest, code_files(list_files(dest)), _repo_name(url))


def _repo_name(url: str) -> str:
    return url.rsplit("/", 1)[-1]  # the URL is normalized: no trailing slash, no .git


def _snapshot_id(session: Session, url: str, sha: str) -> int | None:
    # Served by uq_snapshots_repo_commit after the unique index on repos.url.
    return session.exec(
        select(Snapshot.id).join(Repo, col(Snapshot.repo_id) == col(Repo.id)).where(Repo.url == url, Snapshot.commit_sha == sha)
    ).first()


def _upsert_repo(session: Session, job: IndexJob) -> int:
    row = Repo(url=job.url, status=RepoStatus.indexed, added_by=job.user_id).model_dump(exclude={"id"})
    # A concurrent insert of the same URL blocks here until the other transaction ends, then does nothing.
    inserted = session.exec(
        insert(Repo).values(**row).on_conflict_do_nothing(index_elements=[col(Repo.url)]).returning(col(Repo.id))
    ).scalar_one_or_none()
    repo_id = inserted if inserted is not None else session.exec(select(Repo.id).where(Repo.url == job.url)).one()
    if repo_id is None:
        raise RuntimeError(f"repo {job.url} has no id after insert")
    return repo_id


def _insert_snapshot(session: Session, repo_id: int, sha: str, areas: list[TreeNode]) -> int | None:
    """The new snapshot's id with its tree saved, or None when another worker built this commit first."""
    row = Snapshot(repo_id=repo_id, commit_sha=sha).model_dump(exclude={"id"})  # fills created_at
    snapshot_id: int | None = session.exec(
        insert(Snapshot)
        .values(**row)
        .on_conflict_do_nothing(index_elements=[col(Snapshot.repo_id), col(Snapshot.commit_sha)])
        .returning(col(Snapshot.id))
    ).scalar_one_or_none()
    if snapshot_id is not None:
        save_areas(session, snapshot_id, areas)
    return snapshot_id


def _point(session: Session, repo_id: int, snapshot_id: int, head_seen_at: datetime) -> None:
    # Compare-and-set on the fence. Insert-once rows need no fence, but this is an overwrite: without the check, a
    # slow job that cloned an older HEAD could finish last and roll the repo back. The loser's snapshot stays.
    session.exec(
        update(Repo)
        .where(col(Repo.id) == repo_id, or_(col(Repo.head_seen_at).is_(None), col(Repo.head_seen_at) < head_seen_at))
        .values(current_snapshot_id=snapshot_id, head_seen_at=head_seen_at)
    )
