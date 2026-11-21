from collections.abc import Iterator

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.api.main import app
from app.api.routes.deep_dives import get_html_reader
from app.config import rds
from app.deep_dive.content_security_policy import HTML_CSP
from app.deep_dive.streams import DEEP_DIVE_STREAM, PAYLOAD_FIELD
from app.models import DeepDive, DeepDiveCreate, Grouping, Node, Repo, RepoStatus, Snapshot

PAGE = "<p>the page</p>"


@pytest.fixture
def client() -> Iterator[TestClient]:
    rds.flushdb()
    app.dependency_overrides[get_html_reader] = lambda: {"k.html": PAGE}.__getitem__
    yield TestClient(app)
    app.dependency_overrides.clear()
    rds.flushdb()


@pytest.fixture
def node_id(session: Session) -> int:
    repo = Repo(url="https://github.com/o/r", status=RepoStatus.indexed)
    session.add(repo)
    session.flush()
    assert repo.id is not None
    snapshot = Snapshot(repo_id=repo.id, commit_sha="a" * 40)
    session.add(snapshot)
    session.flush()
    assert snapshot.id is not None
    repo.current_snapshot_id = snapshot.id
    node = Node(name="Queue", paths=["app"], grouping=Grouping.llm, snapshot_id=snapshot.id)
    session.add(node)
    session.commit()
    assert node.id is not None
    return node.id


def test_post_twice_is_accepted_twice_and_queued_once(client: TestClient, node_id: int) -> None:
    for _ in range(2):
        response = client.post(f"/nodes/{node_id}/deep-dive")
        assert response.status_code == status.HTTP_202_ACCEPTED

    [(_, fields)] = rds.xrange(DEEP_DIVE_STREAM)
    job = DeepDiveCreate.model_validate_json(fields[PAYLOAD_FIELD])
    assert (job.snapshot_id, job.node_id) == (1, node_id)


def test_post_for_missing_node_is_404(client: TestClient, session: Session) -> None:
    assert client.post("/nodes/999/deep-dive").status_code == status.HTTP_404_NOT_FOUND
    assert rds.xlen(DEEP_DIVE_STREAM) == 0


def test_get_is_404_until_written_then_serves_page_with_csp(
    client: TestClient, session: Session, node_id: int
) -> None:
    assert client.get(f"/nodes/{node_id}/deep-dive").status_code == status.HTTP_404_NOT_FOUND

    session.add(DeepDive(snapshot_id=1, node_id=node_id, object_key="k.html"))
    session.commit()

    assert client.get(f"/nodes/{node_id}/deep-dive").json()["object_key"] == "k.html"
    html = client.get(f"/nodes/{node_id}/deep-dive/html")
    assert html.text == PAGE
    assert html.headers["content-security-policy"] == HTML_CSP


def test_repo_root_deep_dive_is_queued_once_and_served_apart_from_node_ones(
    client: TestClient, session: Session, node_id: int
) -> None:
    for _ in range(2):
        assert client.post("/repos/1/deep-dive").status_code == status.HTTP_202_ACCEPTED
    [(_, fields)] = rds.xrange(DEEP_DIVE_STREAM)
    job = DeepDiveCreate.model_validate_json(fields[PAYLOAD_FIELD])
    assert (job.snapshot_id, job.node_id) == (1, None)

    session.add(DeepDive(snapshot_id=1, node_id=node_id, object_key="other.html"))
    session.commit()
    assert client.get("/repos/1/deep-dive").status_code == status.HTTP_404_NOT_FOUND  # a node's isn't the root's

    session.add(DeepDive(snapshot_id=1, object_key="k.html"))
    session.commit()
    assert client.get("/repos/1/deep-dive").json()["node_id"] is None
    assert client.get("/repos/1/deep-dive/html").text == PAGE


def test_repo_deep_dive_for_missing_repo_is_404(client: TestClient, session: Session) -> None:
    assert client.post("/repos/999/deep-dive").status_code == status.HTTP_404_NOT_FOUND
    assert rds.xlen(DEEP_DIVE_STREAM) == 0
