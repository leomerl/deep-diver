from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlmodel import Session, col, select

from app.indexing.index_repo import index_repo
from app.models import IndexJob, Edge, EdgeKind, Node, Repo, RepoStatus, Snapshot, TreeNode

URL = "https://github.com/fastapi/fastapi"
SHA = "a" * 40
NEW_SHA = "b" * 40
FILES = ["README.md", "fastapi/main.py", "fastapi/routing.py", "uv.lock"]


class FakeClone:
    def __init__(self, sha: str = SHA) -> None:
        self.sha = sha
        self.calls = 0

    def __call__(self, url: str, dest: Path) -> str:
        self.calls += 1
        return self.sha


def fake_list_files(dest: Path) -> list[str]:
    return FILES


class FakeExplore:
    def __init__(self) -> None:
        self.seen: list[tuple[list[str], str]] = []

    def __call__(self, root: Path, files: list[str], repo_name: str) -> list[TreeNode]:
        self.seen.append((files, repo_name))
        routing = TreeNode(name="Routing", description="Routes requests.", paths=["fastapi/routing.py"])
        return [TreeNode(name="Core", description="The framework.", paths=["fastapi"], children=[routing])]


def _current_sha(session: Session) -> str:
    repo = session.exec(select(Repo)).one()
    session.refresh(repo)
    snapshot = session.get(Snapshot, repo.current_snapshot_id)
    assert snapshot is not None
    return snapshot.commit_sha


def test_saves_indexed_repo_with_areas_and_repeated_job_runs_no_agents(session: Session) -> None:
    clone, explore = FakeClone(), FakeExplore()
    job = IndexJob(url=URL)

    index_repo(session, job, clone, fake_list_files, explore)
    index_repo(session, job, clone, fake_list_files, explore)

    [repo] = session.exec(select(Repo)).all()
    [snapshot] = session.exec(select(Snapshot)).all()
    assert (repo.url, repo.status, repo.current_snapshot_id) == (URL, RepoStatus.indexed, snapshot.id)
    assert snapshot.commit_sha == SHA
    # Lockfiles are filtered out before the agents see the file list; the repeat found its commit built.
    assert explore.seen == [(["README.md", "fastapi/main.py", "fastapi/routing.py"], "fastapi")]
    core, routing = session.exec(select(Node).order_by(col(Node.id))).all()
    assert (core.name, core.paths, core.snapshot_id) == ("Core", ["fastapi"], snapshot.id)
    [edge] = session.exec(select(Edge)).all()
    assert (edge.source_id, edge.target_id, edge.kind) == (core.id, routing.id, EdgeKind.contains)


def test_reindex_builds_a_new_snapshot_and_keeps_the_old_tree(session: Session) -> None:
    explore = FakeExplore()
    index_repo(session, IndexJob(url=URL), FakeClone(SHA), fake_list_files, explore)

    index_repo(session, IndexJob(url=URL), FakeClone(NEW_SHA), fake_list_files, explore)

    assert _current_sha(session) == NEW_SHA
    old, new = session.exec(select(Snapshot).order_by(col(Snapshot.id))).all()
    trees = [n.snapshot_id for n in session.exec(select(Node).order_by(col(Node.id))).all()]
    assert trees == [old.id, old.id, new.id, new.id]


def test_a_job_that_read_head_before_the_last_mover_does_not_move_the_pointer(session: Session) -> None:
    index_repo(session, IndexJob(url=URL), FakeClone(SHA), fake_list_files, FakeExplore())
    repo = session.exec(select(Repo)).one()
    # Stands in for a newer job that read HEAD after this slow one did and already moved the pointer.
    repo.head_seen_at = datetime.now(UTC) + timedelta(hours=1)
    session.commit()

    index_repo(session, IndexJob(url=URL), FakeClone(NEW_SHA), fake_list_files, FakeExplore())

    assert _current_sha(session) == SHA
    assert len(session.exec(select(Snapshot)).all()) == 2  # its tree is kept, just not current
