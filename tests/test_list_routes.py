from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.api.main import app
from app.api.routes.deep_dives import get_html_reader
from app.models import DeepDive, InterviewQuestion, Node, Repo, RepoStatus, Snapshot

client = TestClient(app)


def _repo(session: Session) -> tuple[Repo, Snapshot]:
    """An indexed repo and its current snapshot."""
    repo = Repo(url="https://github.com/o/r", status=RepoStatus.indexed)
    session.add(repo)
    session.flush()
    assert repo.id is not None
    snapshot = Snapshot(repo_id=repo.id, commit_sha="a" * 40)
    session.add(snapshot)
    session.flush()
    repo.current_snapshot_id = snapshot.id
    return repo, snapshot


def _deep_dive(session: Session, snapshot: Snapshot, name: str | None, created_at: datetime) -> DeepDive:
    """A deep dive on a new node called `name`; None makes the snapshot's root deep dive."""
    assert snapshot.id is not None
    node = None if name is None else Node(name=name, paths=[name.lower()], snapshot_id=snapshot.id)
    if node is not None:
        session.add(node)
        session.flush()
    node_id = None if node is None else node.id
    dive = DeepDive(snapshot_id=snapshot.id, node_id=node_id, object_key=f"{name}.html", created_at=created_at)
    session.add(dive)
    session.flush()
    return dive


def test_lists_deep_dives_newest_first_with_their_labels(session: Session) -> None:
    _, snapshot = _repo(session)
    now = datetime.now(UTC)
    _deep_dive(session, snapshot, "Old", now - timedelta(days=1))
    _deep_dive(session, snapshot, "New", now)
    _deep_dive(session, snapshot, None, now + timedelta(days=1))
    session.commit()

    body = client.get("/deep-dives").json()
    assert [(d["node_name"], d["repo_url"], d["object_key"], d["stale"]) for d in body] == [
        (None, "https://github.com/o/r", "None.html", False),
        ("New", "https://github.com/o/r", "New.html", False),
        ("Old", "https://github.com/o/r", "Old.html", False),
    ]


def test_deep_dives_of_an_older_snapshot_are_stale_and_still_served(session: Session) -> None:
    repo, old = _repo(session)
    dive = _deep_dive(session, old, None, datetime.now(UTC))
    newer = Snapshot(repo_id=old.repo_id, commit_sha="b" * 40)
    session.add(newer)
    session.flush()
    repo.current_snapshot_id = newer.id  # re-indexed
    session.commit()
    app.dependency_overrides[get_html_reader] = lambda: {"None.html": "<p>old page</p>"}.__getitem__
    try:
        [item] = client.get("/deep-dives").json()
        page = client.get(f"/deep-dives/{dive.id}/html")
    finally:
        app.dependency_overrides.clear()

    assert item["stale"] is True
    assert page.text == "<p>old page</p>"
    # The repo route serves the current snapshot's root page, which isn't written yet.
    assert client.get(f"/repos/{repo.id}/deep-dive").status_code == 404
    assert client.get("/deep-dives/999/html").status_code == 404


def test_lists_every_interview_question_with_its_area(session: Session) -> None:
    repo, snapshot = _repo(session)
    dive = _deep_dive(session, snapshot, "Queue", datetime.now(UTC))
    assert dive.id is not None
    session.add_all([
        InterviewQuestion(deep_dive_id=dive.id, question="Why streams?", answer="Consumer groups."),
        InterviewQuestion(deep_dive_id=dive.id, question="What if a worker dies?", answer="The reaper reclaims it."),
    ])
    session.commit()

    body = client.get("/interview-questions").json()
    assert [(q["question"], q["repo_id"], q["node_id"], q["node_name"], q["repo_url"]) for q in body] == [
        ("Why streams?", repo.id, dive.node_id, "Queue", "https://github.com/o/r"),
        ("What if a worker dies?", repo.id, dive.node_id, "Queue", "https://github.com/o/r"),
    ]


NOTEBOOK_JSON = '{"title": "Run it", "cells": [{"explanation": "Go.", "code": "print(1)", "mirrors": null}]}'


def test_notebook_is_served_typed_and_404_without_one(session: Session) -> None:
    _, snapshot = _repo(session)
    with_notebook = _deep_dive(session, snapshot, "Queue", datetime.now(UTC))
    with_notebook.notebook_key = "nb.json"
    without = _deep_dive(session, snapshot, None, datetime.now(UTC))
    session.commit()
    app.dependency_overrides[get_html_reader] = lambda: {"nb.json": NOTEBOOK_JSON}.__getitem__
    try:
        ok = client.get(f"/deep-dives/{with_notebook.id}/notebook")
        missing = client.get(f"/deep-dives/{without.id}/notebook")
    finally:
        app.dependency_overrides.clear()

    assert ok.json() == {"title": "Run it", "cells": [{"explanation": "Go.", "code": "print(1)", "mirrors": None}]}
    assert missing.status_code == 404
    assert client.get("/deep-dives/999/notebook").status_code == 404


def test_requesting_a_notebook_queues_it_once_and_404s_for_a_missing_page(session: Session) -> None:
    from app.config import rds
    from app.deep_dive.streams import NOTEBOOK_STREAM

    rds.flushdb()
    _, snapshot = _repo(session)
    dive = _deep_dive(session, snapshot, "Queue", datetime.now(UTC))
    session.commit()

    assert client.post(f"/deep-dives/{dive.id}/notebook").json() == {"deep_dive_id": dive.id}
    assert client.post(f"/deep-dives/{dive.id}/notebook").status_code == 202
    assert rds.xlen(NOTEBOOK_STREAM) == 1  # the second request found the dedup marker
    assert client.post("/deep-dives/999/notebook").status_code == 404
    rds.flushdb()
