from collections.abc import Iterator

import pytest

from app.config import rds
from app.queue import ack, ensure_group, read_one

STREAM = "test:jobs"
GROUP = "test-group"
CONSUMER = "test-consumer"
NO_WAIT_MS = 1


@pytest.fixture(autouse=True)
def clean_redis() -> Iterator[None]:
    rds.flushdb()
    yield
    rds.flushdb()


def test_read_then_ack_clears_pending() -> None:
    ensure_group(rds, STREAM, GROUP)
    ensure_group(rds, STREAM, GROUP)  # second call on restart must not fail
    entry_id = rds.xadd(STREAM, {"payload": "hello"})

    assert read_one(rds, STREAM, GROUP, CONSUMER, NO_WAIT_MS) == (entry_id, {"payload": "hello"})
    assert rds.xpending(STREAM, GROUP)["pending"] == 1

    ack(rds, STREAM, GROUP, entry_id)
    assert rds.xpending(STREAM, GROUP)["pending"] == 0


def test_empty_stream_returns_none() -> None:
    ensure_group(rds, STREAM, GROUP)
    assert read_one(rds, STREAM, GROUP, CONSUMER, NO_WAIT_MS) is None
