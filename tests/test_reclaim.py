import time
from collections.abc import Iterator

import pytest

from app.config import rds
from app.queue import ensure_group, read_one, reclaim_one

STREAM = "test:jobs"
GROUP = "test-group"
CRASHED = "crashed"
RESCUER = "rescuer"
MIN_IDLE_MS = 100
NO_WAIT_MS = 1
MS_PER_S = 1000


@pytest.fixture(autouse=True)
def clean_redis() -> Iterator[None]:
    rds.flushdb()
    yield
    rds.flushdb()


def _taken_by_crashed() -> str:
    ensure_group(rds, STREAM, GROUP)
    entry_id = rds.xadd(STREAM, {"payload": "x"})
    assert read_one(rds, STREAM, GROUP, CRASHED, NO_WAIT_MS) is not None
    return entry_id


def test_fresh_entry_is_left_alone() -> None:
    _taken_by_crashed()
    assert reclaim_one(rds, STREAM, GROUP, RESCUER, MIN_IDLE_MS) is None


def test_idle_entry_is_taken_over_with_its_delivery_count() -> None:
    entry_id = _taken_by_crashed()
    time.sleep(MIN_IDLE_MS * 2 / MS_PER_S)

    assert reclaim_one(rds, STREAM, GROUP, RESCUER, MIN_IDLE_MS) == (entry_id, {"payload": "x"}, 2)
    [pending] = rds.xpending_range(STREAM, GROUP, entry_id, entry_id, 1)
    assert pending["consumer"] == RESCUER
