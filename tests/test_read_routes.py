import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.api.main import app
from app.indexing.save_areas import save_areas
from app.models import Edge, EdgeKind, Grouping, Node, Repo, RepoStatus, Snapshot, TreeNode

client = TestClient(app)
TREE = [
    TreeNode(name="API", description="HTTP layer.", paths=["api"], children=[
        TreeNode(name="Auth", description="Login.", paths=["api/auth"]),
        TreeNode(name="routes", description="By folder.", paths=["api/routes"], grouping=Grouping.fallback),
    ]),
    TreeNode(name="Worker", description="Background jobs.", paths=["worker"]),
]


def _add_repo(session: Session, name: str, repo_status: RepoStatus, areas: list[TreeNode]) -> int:
    repo = Repo(url=f"https://github.com/o/{name}", status=repo_status)
    session.add(repo)
    session.flush()
    _add_snapshot(session, repo, "a", areas)
    assert repo.id is not None
    return repo.id


def _add_snapshot(session: Session, repo: Repo, sha_char: str, areas: list[TreeNode]) -> int:
    """A snapshot with its tree, made the repo's current one."""
    assert repo.id is not None
    snapshot = Snapshot(repo_id=repo.id, commit_sha=sha_char * 40)
    session.add(snapshot)
    session.flush()
    assert snapshot.id is not None
    save_areas(session, snapshot.id, areas)
    repo.current_snapshot_id = snapshot.id
    session.commit()
    return snapshot.id


def test_lists_only_indexed_repos(session: Session) -> None:
    indexed = _add_repo(session, "done", RepoStatus.indexed, [])
    _add_repo(session, "busy", RepoStatus.indexing, [])

    assert [r["id"] for r in client.get("/repos").json()] == [indexed]


def test_map_returns_nodes_and_contains_edges_and_node_returns_children(session: Session) -> None:
    repo_id = _add_repo(session, "r", RepoStatus.indexed, TREE)

    body = client.get(f"/repos/{repo_id}/map").json()
    ids = {node["name"]: node["id"] for node in body["nodes"]}
    assert [(n["name"], n["paths"], n["grouping"]) for n in body["nodes"]] == [
        ("API", ["api"], "llm"), ("Worker", ["worker"], "llm"),
        ("Auth", ["api/auth"], "llm"), ("routes", ["api/routes"], "fallback"),
    ]
    assert [(e["source_id"], e["target_id"], e["kind"]) for e in body["edges"]] == [
        (ids["API"], ids["Auth"], "contains"), (ids["API"], ids["routes"], "contains"),
    ]

    node = client.get(f"/nodes/{ids['API']}").json()
    assert (node["name"], [c["name"] for c in node["children"]]) == ("API", ["Auth", "routes"])


def test_map_shows_only_the_current_snapshot(session: Session) -> None:
    repo_id = _add_repo(session, "r", RepoStatus.indexed, TREE)
    repo = session.get(Repo, repo_id)
    assert repo is not None
    _add_snapshot(session, repo, "b", [TreeNode(name="Rewritten", description="After a re-index.", paths=["src"])])

    body = client.get(f"/repos/{repo_id}/map").json()
    assert [n["name"] for n in body["nodes"]] == ["Rewritten"]
    assert body["edges"] == []
    assert client.get("/repos").json()[0]["commit_sha"] == "b" * 40


def test_missing_or_unindexed_is_404(session: Session) -> None:
    busy = _add_repo(session, "busy", RepoStatus.indexing, [])

    assert client.get(f"/repos/{busy}/map").status_code == status.HTTP_404_NOT_FOUND
    assert client.get("/repos/999/map").status_code == status.HTTP_404_NOT_FOUND
    assert client.get("/nodes/999").status_code == status.HTTP_404_NOT_FOUND


def test_database_refuses_a_second_parent(session: Session) -> None:
    _add_repo(session, "r", RepoStatus.indexed, TREE)
    ids = {node.name: node.id for node in session.exec(select(Node)).all()}

    # Auth already has API as its parent.
    session.add(Edge(source_id=ids["Worker"], target_id=ids["Auth"], kind=EdgeKind.contains))
    with pytest.raises(IntegrityError, match="ux_edges_one_parent"):
        session.commit()


def test_database_refuses_an_area_without_paths(session: Session) -> None:
    _add_repo(session, "r", RepoStatus.indexed, [])
    session.add(Node(name="Empty", paths=[], snapshot_id=session.exec(select(Snapshot.id)).one()))
    with pytest.raises(IntegrityError, match="ck_nodes_has_paths"):
        session.commit()
