from collections.abc import Iterator

import pytest

from app.config import rds
from app.queue import JobState, ack, dead_letter, ensure_group, read_one, stream_jobs

STREAM = "test:jobs"
GROUP = "test-group"
DLQ = "test:dead"
CONSUMER = "test-consumer"
LEASE_MS = 60_000


@pytest.fixture(autouse=True)
def clean_redis() -> Iterator[None]:
    rds.flushdb()
    yield
    rds.flushdb()


def test_each_state_is_derived_from_the_group_and_the_dlq() -> None:
    ids = [rds.xadd(STREAM, {"payload": str(n)}) for n in range(4)]
    ensure_group(rds, STREAM, GROUP)
    for _ in range(3):  # the first three are delivered, the fourth stays queued
        read_one(rds, STREAM, GROUP, CONSUMER, 10)
    ack(rds, STREAM, GROUP, ids[0])
    dead_letter(rds, STREAM, GROUP, ids[1], {"payload": "1"}, DLQ)

    jobs = stream_jobs(rds, STREAM, GROUP, DLQ, LEASE_MS, 10)

    assert [(j.entry_id, j.state, j.deliveries, j.consumer) for j in jobs] == [
        (ids[3], JobState.queued, None, None),
        (ids[2], JobState.running, 1, CONSUMER),
        (ids[1], JobState.dead, None, None),
        (ids[0], JobState.done, None, None),
    ]


def test_a_pending_job_idle_past_its_lease_is_retrying() -> None:
    rds.xadd(STREAM, {"payload": "x"})
    ensure_group(rds, STREAM, GROUP)
    read_one(rds, STREAM, GROUP, CONSUMER, 10)

    [job] = stream_jobs(rds, STREAM, GROUP, DLQ, 0, 10)
    assert job.state == JobState.retrying


def test_jobs_queued_before_any_worker_are_queued_and_no_stream_is_no_jobs() -> None:
    assert stream_jobs(rds, STREAM, GROUP, DLQ, LEASE_MS, 10) == []
    rds.xadd(STREAM, {"payload": "x"})
    assert [j.state for j in stream_jobs(rds, STREAM, GROUP, DLQ, LEASE_MS, 10)] == [JobState.queued]


def test_only_the_newest_count_are_read() -> None:
    ids = [rds.xadd(STREAM, {"payload": str(n)}) for n in range(3)]
    assert [j.entry_id for j in stream_jobs(rds, STREAM, GROUP, DLQ, LEASE_MS, 2)] == [ids[2], ids[1]]
