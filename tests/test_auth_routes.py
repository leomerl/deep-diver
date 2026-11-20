from collections.abc import Iterator
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlmodel import Session

import app.api.routes.auth as auth_route
from app.api.main import app
from app.github import GitHubRepo, GitHubUser

TOKEN = "gho_test"
REPO = GitHubRepo(full_name="omer/secret", html_url="https://github.com/omer/secret", private=True)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, session: Session) -> Iterator[TestClient]:
    monkeypatch.setattr(auth_route, "GITHUB_CLIENT_ID", "cid")
    monkeypatch.setattr(auth_route, "exchange_code", lambda cid, secret, code, timeout_s: TOKEN)
    monkeypatch.setattr(auth_route, "get_user", lambda token, timeout_s: GitHubUser(id=42, login="omer"))

    def repos(token: str, timeout_s: float) -> list[GitHubRepo]:
        assert token == TOKEN  # proves the stored token decrypts back to what GitHub gave us
        return [REPO]

    monkeypatch.setattr(auth_route, "list_repos", repos)
    yield TestClient(app, follow_redirects=False)


def login(client: TestClient) -> None:
    redirect = client.get("/auth/github/login")
    assert redirect.status_code == status.HTTP_307_TEMPORARY_REDIRECT
    [state] = parse_qs(urlsplit(redirect.headers["location"]).query)["state"]
    done = client.get("/auth/github/callback", params={"code": "c", "state": state})
    assert done.status_code == status.HTTP_307_TEMPORARY_REDIRECT
    assert done.headers["location"] == "/"


def test_login_sets_a_session_and_lists_the_users_github_repos(client: TestClient) -> None:
    assert client.get("/auth/me").json() is None
    assert client.get("/auth/github/repos").status_code == status.HTTP_401_UNAUTHORIZED
    login(client)
    login(client)  # again: same user row, refreshed token
    assert client.get("/auth/me").json() == {"id": 1, "github_id": 42, "login": "omer"}
    assert client.get("/auth/github/repos").json() == [REPO.model_dump()]


def test_wrong_state_is_rejected(client: TestClient) -> None:
    client.get("/auth/github/login")
    response = client.get("/auth/github/callback", params={"code": "c", "state": "forged"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert client.get("/auth/me").json() is None
