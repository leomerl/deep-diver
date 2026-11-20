from collections.abc import Iterator

import pytest

from app.config import rds
from app.queue import DEDUP_KEY_FIELD, ORIGINAL_ID_FIELD, dead_letter, enqueue_once, ensure_group, read_one

STREAM = "test:jobs"
DLQ = "test:dead"
GROUP = "test-group"
CONSUMER = "test-consumer"
DEDUP_KEY = "test:dedup:1"
NO_WAIT_MS = 1


@pytest.fixture(autouse=True)
def clean_redis() -> Iterator[None]:
    rds.flushdb()
    yield
    rds.flushdb()


def test_dead_letter_moves_acks_and_frees_the_marker() -> None:
    ensure_group(rds, STREAM, GROUP)
    assert enqueue_once(rds, DEDUP_KEY, STREAM, {"payload": "x"})
    entry = read_one(rds, STREAM, GROUP, CONSUMER, NO_WAIT_MS)
    assert entry is not None
    entry_id, fields = entry
    assert fields == {"payload": "x", DEDUP_KEY_FIELD: DEDUP_KEY}

    dead_letter(rds, STREAM, GROUP, entry_id, fields, DLQ)

    [(_, dead)] = rds.xrange(DLQ)
    assert dead == {**fields, ORIGINAL_ID_FIELD: entry_id}
    assert rds.xpending(STREAM, GROUP)["pending"] == 0
    assert rds.exists(DEDUP_KEY) == 0
    assert enqueue_once(rds, DEDUP_KEY, STREAM, {"payload": "x"})  # the job can be queued again
