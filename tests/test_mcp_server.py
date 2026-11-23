from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from mcp.server.mcpserver.exceptions import ToolError
from sqlmodel import Session

from app.api.main import app
from app.mcp_server import repo_outline, server as mcp_tools
from app.mcp_server.tools import get_map, list_deep_dives, list_repos, read_deep_dive
from app.models import DeepDive, Edge, EdgeKind, EdgeRead, Node, NodeRead, Repo, RepoMap, RepoStatus, Snapshot

RPC_HEADERS = {"Accept": "application/json, text/event-stream"}


def test_outline_nests_children_and_marks_written_pages() -> None:
    repo_map = RepoMap(
        nodes=[
            NodeRead(id=1, name="API", description="HTTP routes", paths=["app/api"]),
            NodeRead(id=2, name="Auth", paths=["app/auth", "app/api/routes/auth.py"]),
            NodeRead(id=3, name="Queue", paths=["app/queue"]),
        ],
        edges=[EdgeRead(id=1, source_id=1, target_id=2, kind=EdgeKind.contains)],
    )

    assert repo_outline(repo_map, {None: 9, 2: 7}).splitlines() == [
        "whole repo (deep dive 9)",
        "- API (node 1, no deep dive) [app/api]: HTTP routes",
        "  - Auth (node 2, deep dive 7) [app/auth, app/api/routes/auth.py]",
        "- Queue (node 3, no deep dive) [app/queue]",
    ]


def _indexed_repo(session: Session) -> tuple[int, int, int]:
    """An indexed repo with areas API > Auth, a root page and a page on Auth. Returns (repo, root page, Auth page) ids."""
    repo = Repo(url="https://github.com/o/r", status=RepoStatus.indexed)
    session.add(repo)
    session.flush()
    assert repo.id is not None
    snapshot = Snapshot(repo_id=repo.id, commit_sha="a" * 40)
    session.add(snapshot)
    session.flush()
    assert snapshot.id is not None
    repo.current_snapshot_id = snapshot.id
    api = Node(name="API", paths=["app/api"], snapshot_id=snapshot.id)
    auth = Node(name="Auth", paths=["app/auth"], snapshot_id=snapshot.id)
    session.add_all([api, auth])
    session.flush()
    assert api.id is not None and auth.id is not None
    session.add(Edge(source_id=api.id, target_id=auth.id, kind=EdgeKind.contains))
    root = DeepDive(snapshot_id=snapshot.id, node_id=None, object_key="root.html", created_at=datetime.now(UTC))
    page = DeepDive(snapshot_id=snapshot.id, node_id=auth.id, object_key="auth.html", created_at=datetime.now(UTC))
    session.add_all([root, page])
    session.commit()
    assert root.id is not None and page.id is not None
    return repo.id, root.id, page.id


def test_tools_walk_from_repo_to_page_text(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_id, root_id, page_id = _indexed_repo(session)
    pages = {"auth.html": "<h1>Auth</h1><style>p{}</style><p>Signs the cookie.</p>"}
    monkeypatch.setattr("app.mcp_server.tools.get_html_reader", lambda: pages.__getitem__)

    assert [(repo.id, repo.commit_sha) for repo in list_repos()] == [(repo_id, "a" * 40)]
    outline = get_map(repo_id)
    assert outline.splitlines()[0] == f"whole repo (deep dive {root_id})"
    assert f"  - Auth (node 2, deep dive {page_id}) [app/auth]" in outline
    assert {(dive.id, dive.node_name) for dive in list_deep_dives()} == {(root_id, None), (page_id, "Auth")}
    assert read_deep_dive(page_id) == "Auth\n\nSigns the cookie."


def test_unknown_ids_are_tool_errors_the_agent_can_read(session: Session) -> None:
    with pytest.raises(ToolError, match="repo not found"):
        get_map(999)
    with pytest.raises(ToolError, match="deep dive not found"):
        read_deep_dive(999)


def test_mcp_endpoint_lists_the_tools_over_http() -> None:
    # The only test that enters the lifespan: the SDK's session manager runs once per process.
    # base_url: the transport rejects any Host but localhost (DNS rebinding protection).
    with TestClient(app, base_url="http://localhost:8000") as client:
        response = client.post("/mcp", headers=RPC_HEADERS, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        foreign = client.post(
            "/mcp", headers={**RPC_HEADERS, "Host": "evil.example"}, json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
        )

    assert {tool["name"] for tool in response.json()["result"]["tools"]} == {
        "list_repos", "get_map", "list_deep_dives", "read_deep_dive",
    }
    assert foreign.status_code == 421
    assert mcp_tools.name == "deep-diver"
