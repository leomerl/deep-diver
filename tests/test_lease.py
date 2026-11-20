import time
from collections.abc import Iterator

import pytest

from app.config import rds
from app.queue import ensure_group, lease, read_one

STREAM = "test:jobs"
GROUP = "test-group"
ME = "me"
OTHER = "other"
LEASE_S = 0.3
NO_WAIT_MS = 1
MS_PER_S = 1000


@pytest.fixture(autouse=True)
def clean_redis() -> Iterator[None]:
    rds.flushdb()
    yield
    rds.flushdb()


def _taken() -> str:
    ensure_group(rds, STREAM, GROUP)
    rds.xadd(STREAM, {"payload": "x"})
    entry = read_one(rds, STREAM, GROUP, ME, NO_WAIT_MS)
    assert entry is not None
    return entry[0]


def _pending(entry_id: str) -> dict[str, str | int]:
    [pending] = rds.xpending_range(STREAM, GROUP, entry_id, entry_id, 1)
    return pending


def test_held_lease_keeps_the_entry_fresh() -> None:
    entry_id = _taken()
    with lease(rds, STREAM, GROUP, ME, entry_id, LEASE_S):
        time.sleep(LEASE_S * 2)
        assert int(_pending(entry_id)["time_since_delivered"]) < LEASE_S * MS_PER_S
    assert _pending(entry_id)["times_delivered"] == 1  # renewals don't count as deliveries


def test_lease_does_not_take_back_a_reclaimed_entry() -> None:
    entry_id = _taken()
    with lease(rds, STREAM, GROUP, ME, entry_id, LEASE_S):
        rds.xclaim(STREAM, GROUP, OTHER, 0, [entry_id], justid=True)
        time.sleep(LEASE_S)  # several renewal periods
        assert _pending(entry_id)["consumer"] == OTHER
