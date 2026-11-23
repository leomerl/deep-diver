from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.api.main import app
from app.config import engine, rds
from app.deep_dive.streams import DEEP_DIVE_GROUP, DEEP_DIVE_STREAM, NOTEBOOK_STREAM
from app.indexing.streams import INDEX_STREAM
from app.jobs import record_job_event
from app.models import DeepDive, DeepDiveCreate, IndexJob, Node, NotebookJob, Repo, RepoStatus, Snapshot
from app.queue import JobEventKind, ensure_group, read_one

client = TestClient(app)
WORKER = "host-1"


@pytest.fixture(autouse=True)
def clean_redis() -> Iterator[None]:
    rds.flushdb()
    yield
    rds.flushdb()


def _node(session: Session) -> Node:
    repo = Repo(url="https://github.com/o/r", status=RepoStatus.indexed)
    session.add(repo)
    session.flush()
    assert repo.id is not None
    snapshot = Snapshot(repo_id=repo.id, commit_sha="a" * 40)
    session.add(snapshot)
    session.flush()
    assert snapshot.id is not None
    node = Node(name="Queue", paths=["app/queue"], snapshot_id=snapshot.id)
    session.add(node)
    session.commit()
    return node


def test_lists_both_queues_newest_first_with_state_steps_and_history(session: Session) -> None:
    node = _node(session)
    index_id = rds.xadd(INDEX_STREAM, {"payload": IndexJob(url="https://github.com/o/r").model_dump_json()})
    dive_id = rds.xadd(DEEP_DIVE_STREAM, {"payload": DeepDiveCreate(snapshot_id=node.snapshot_id, node_id=node.id).model_dump_json()})
    ensure_group(rds, DEEP_DIVE_STREAM, DEEP_DIVE_GROUP)
    read_one(rds, DEEP_DIVE_STREAM, DEEP_DIVE_GROUP, WORKER, 10)
    record_job_event(engine, DEEP_DIVE_STREAM, WORKER, dive_id, JobEventKind.started, 1, None)
    record_job_event(engine, DEEP_DIVE_STREAM, WORKER, dive_id, JobEventKind.step, 1, "write")

    dive, index = client.get("/jobs").json()

    assert (dive["entry_id"], dive["label"], dive["state"], dive["deliveries"], dive["consumer"]) == (
        dive_id, "r > Queue", "running", 1, WORKER,
    )
    assert [(s["name"], s["status"]) for s in dive["chain"]] == [("write", "passed"), ("verify", "running"), ("notebook", "waiting")]
    assert [(e["kind"], e["detail"]) for e in dive["events"]] == [("started", None), ("step", "write")]
    assert (index["entry_id"], index["label"], index["state"], index["deliveries"], index["chain"]) == (
        index_id, "https://github.com/o/r", "queued", 0, [],
    )


def test_a_finished_job_keeps_its_tries_and_error_from_history(session: Session) -> None:
    entry_id = rds.xadd(DEEP_DIVE_STREAM, {"payload": "not json"})
    ensure_group(rds, DEEP_DIVE_STREAM, DEEP_DIVE_GROUP)
    read_one(rds, DEEP_DIVE_STREAM, DEEP_DIVE_GROUP, WORKER, 10)
    rds.xack(DEEP_DIVE_STREAM, DEEP_DIVE_GROUP, entry_id)
    for event in [(JobEventKind.started, 1, None), (JobEventKind.failed, 1, "AgentSdkError: boom"),
                  (JobEventKind.started, 2, None), (JobEventKind.done, 2, None)]:
        record_job_event(engine, DEEP_DIVE_STREAM, WORKER, entry_id, *event)

    [job] = client.get("/jobs").json()

    assert (job["label"], job["state"], job["deliveries"]) == ("(unreadable or removed)", "done", 2)
    assert [e["detail"] for e in job["events"] if e["kind"] == "failed"] == ["AgentSdkError: boom"]


def test_a_notebook_job_is_the_last_link_of_its_deep_dive_or_listed_alone(session: Session) -> None:
    node = _node(session)
    page = DeepDive(snapshot_id=node.snapshot_id, node_id=node.id, object_key="p.html")
    session.add(page)
    session.commit()
    assert page.id is not None
    target = DeepDiveCreate(snapshot_id=node.snapshot_id, node_id=node.id)
    rds.xadd(DEEP_DIVE_STREAM, {"payload": target.model_dump_json()})
    notebook_id = rds.xadd(NOTEBOOK_STREAM, {"payload": NotebookJob(deep_dive_id=page.id).model_dump_json()})
    rds.xadd(NOTEBOOK_STREAM, {"payload": NotebookJob(deep_dive_id=999).model_dump_json()})

    # Looked up by stream, not by position: jobs queued in the same millisecond tie in the newest-first sort.
    jobs = {job["stream"]: job for job in client.get("/jobs").json()}
    orphan, dive = jobs[NOTEBOOK_STREAM], jobs[DEEP_DIVE_STREAM]
    assert len(jobs) == 2

    assert dive["chain"][-1] == {"name": "notebook", "status": "waiting"}  # its notebook job is queued
    assert (dive["follow_up"]["entry_id"], dive["follow_up"]["label"]) == (notebook_id, "r > Queue")
    assert (orphan["stream"], orphan["label"], orphan["chain"]) == (NOTEBOOK_STREAM, "(unreadable or removed)", [])
