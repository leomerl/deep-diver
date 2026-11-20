from pathlib import Path

from sqlmodel import Session, col, select

from app.indexing.index_repo import index_repo
from app.models import IndexJob, Edge, EdgeKind, Node, Repo, RepoCreate, RepoStatus, TreeNode

URL = "https://github.com/fastapi/fastapi"
SHA = "a" * 40
FILES = ["README.md", "fastapi/main.py", "fastapi/routing.py", "uv.lock"]


class FakeClone:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, url: str, dest: Path) -> str:
        self.calls += 1
        return SHA


def fake_list_files(dest: Path) -> list[str]:
    return FILES


class FakeExplore:
    def __init__(self) -> None:
        self.seen: list[tuple[list[str], str]] = []

    def __call__(self, root: Path, files: list[str], repo_name: str) -> list[TreeNode]:
        self.seen.append((files, repo_name))
        routing = TreeNode(name="Routing", description="Routes requests.", paths=["fastapi/routing.py"])
        return [TreeNode(name="Core", description="The framework.", paths=["fastapi"], children=[routing])]


def test_saves_indexed_repo_with_areas_and_repeated_job_does_nothing(session: Session) -> None:
    clone, explore = FakeClone(), FakeExplore()
    job = IndexJob(url=URL)

    index_repo(session, job, clone, fake_list_files, explore)
    index_repo(session, job, clone, fake_list_files, explore)

    [repo] = session.exec(select(Repo)).all()
    assert (repo.url, repo.commit_sha, repo.status) == (URL, SHA, RepoStatus.indexed)
    assert clone.calls == 1
    # Lockfiles are filtered out before the agents see the file list.
    assert explore.seen == [(["README.md", "fastapi/main.py", "fastapi/routing.py"], "fastapi")]
    core, routing = session.exec(select(Node).order_by(col(Node.id))).all()
    assert (core.name, core.paths, core.repo_id) == ("Core", ["fastapi"], repo.id)
    [edge] = session.exec(select(Edge)).all()
    assert (edge.source_id, edge.target_id, edge.kind) == (core.id, routing.id, EdgeKind.contains)
