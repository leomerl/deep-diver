from collections.abc import Callable
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, col, select

from app.indexing.code_files import code_files
from app.indexing.save_areas import save_areas
from app.models import IndexJob, Repo, RepoStatus, TreeNode

Clone = Callable[[str, Path], str]  # (url, dest) -> commit SHA
ListFiles = Callable[[Path], list[str]]  # checkout dir -> tracked paths
Explore = Callable[[Path, list[str], str], list[TreeNode]]  # (checkout, code files, repo name) -> top-level areas


def index_repo(session: Session, job: IndexJob, clone: Clone, list_files: ListFiles, explore: Explore) -> None:
    """Clone the repo, map it into areas and save both. A repeated job is a no-op."""
    # Delivery is at-least-once: a job can come back after a crash between commit and XACK.
    if _is_indexed(session, job.url):
        return
    sha, areas = _checkout_and_explore(job.url, clone, list_files, explore)
    _save(session, job, sha, areas)


def _is_indexed(session: Session, url: str) -> bool:
    return session.exec(select(Repo.commit_sha).where(Repo.url == url)).first() is not None


def _checkout_and_explore(url: str, clone: Clone, list_files: ListFiles, explore: Explore) -> tuple[str, list[TreeNode]]:
    with TemporaryDirectory() as tmp:
        dest = Path(tmp) / "repo"
        sha = clone(url, dest)
        # The agents read the checkout through their tools, so it has to exist until exploring ends.
        return sha, explore(dest, code_files(list_files(dest)), _repo_name(url))


def _repo_name(url: str) -> str:
    return url.rsplit("/", 1)[-1]  # the URL is normalized: no trailing slash, no .git


def _save(session: Session, job: IndexJob, sha: str, areas: list[TreeNode]) -> None:
    # Repo and areas commit together: a repo is never visible as indexed with a missing or partial tree.
    row = Repo(url=job.url, commit_sha=sha, status=RepoStatus.indexed, added_by=job.user_id).model_dump(exclude={"id"})
    repo_id = session.exec(
        insert(Repo).values(**row).on_conflict_do_nothing(index_elements=[col(Repo.url)]).returning(col(Repo.id))
    ).scalar_one_or_none()
    # None: another worker raced us and won. Its SHA and tree stay; ours would be a duplicate tree.
    if repo_id is None:
        session.rollback()
        return
    save_areas(session, repo_id, areas)
    session.commit()
