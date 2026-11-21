from collections.abc import Iterator

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from app.api.main import app
from app.config import rds
from app.settings import get_agent_runtime


@pytest.fixture
def client() -> Iterator[TestClient]:
    rds.flushdb()
    yield TestClient(app)
    rds.flushdb()


def test_default_is_the_gateway(client: TestClient) -> None:
    assert client.get("/settings").json() == {"agent_runtime": "gateway"}


def test_put_changes_what_the_workers_read(client: TestClient) -> None:
    response = client.put("/settings", json={"agent_runtime": "agent_sdk"})
    assert response.status_code == status.HTTP_200_OK
    assert client.get("/settings").json() == {"agent_runtime": "agent_sdk"}
    assert get_agent_runtime(rds) == "agent_sdk"  # the worker-side read, same key


def test_unknown_runtime_is_rejected(client: TestClient) -> None:
    assert client.put("/settings", json={"agent_runtime": "openai"}).status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert client.get("/settings").json() == {"agent_runtime": "gateway"}
