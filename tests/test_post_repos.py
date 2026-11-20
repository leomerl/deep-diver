from collections.abc import Iterator
from subprocess import CalledProcessError

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlmodel import Session

import app.api.routes.repos as repos_route
from app.api.main import app
from app.config import rds
from app.indexing.streams import INDEX_STREAM, PAYLOAD_FIELD
from app.models import RepoCreate

CANONICAL = "https://github.com/fastapi/fastapi"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, session: Session) -> Iterator[TestClient]:
    # The route checks the remote with git before queueing; tests must not depend on GitHub.
    monkeypatch.setattr(repos_route, "ls_remote", lambda url, timeout_s, env: None)
    rds.flushdb()
    yield TestClient(app)
    rds.flushdb()


def test_same_repo_twice_is_accepted_twice_and_queued_once(client: TestClient) -> None:
    for url in [CANONICAL, "https://GitHub.com/fastapi/fastapi.git/"]:
        response = client.post("/repos", json={"url": url})
        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.json() == {"url": CANONICAL}

    [(_, fields)] = rds.xrange(INDEX_STREAM)
    assert RepoCreate.model_validate_json(fields[PAYLOAD_FIELD]).url == CANONICAL


def test_invalid_url_is_rejected_and_not_queued(client: TestClient) -> None:
    response = client.post("/repos", json={"url": "https://internal.corp/a/b"})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert rds.xlen(INDEX_STREAM) == 0


def test_unreadable_repo_is_rejected_with_git_reason_and_not_queued(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def private(url: str, timeout_s: float, env: dict[str, str]) -> None:
        e = CalledProcessError(128, ["git"])
        e.add_note("remote: Invalid username or token.\nfatal: Authentication failed for 'x'")
        raise e

    monkeypatch.setattr(repos_route, "ls_remote", private)
    response = client.post("/repos", json={"url": CANONICAL})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "fatal: Authentication failed for 'x'"
    assert rds.xlen(INDEX_STREAM) == 0
