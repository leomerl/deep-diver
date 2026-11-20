import threading
import time
from collections.abc import Iterator
from contextlib import AbstractContextManager

import pytest

from app.config import rds
from app.queue import semaphore_slot

KEY = "test:slots"
LIMIT = 3
POLL_S = 0.02
LEASE_S = 0.6
WAIT_S = 0.3  # long enough for a waiting thread to have entered if the limit were broken
MS_PER_S = 1000


@pytest.fixture(autouse=True)
def clean_redis() -> Iterator[None]:
    rds.flushdb()
    yield
    rds.flushdb()


def _slot() -> AbstractContextManager[None]:
    return semaphore_slot(rds, KEY, LIMIT, LEASE_S, POLL_S)


def _redis_now_ms() -> int:
    seconds, micros = rds.time()
    return seconds * MS_PER_S + micros // MS_PER_S


def test_a_fourth_holder_waits_until_a_slot_is_released() -> None:
    release = [threading.Event() for _ in range(LIMIT)]
    inside = threading.Semaphore(0)

    def hold(done: threading.Event) -> None:
        with _slot():
            inside.release()
            done.wait()

    holders = [threading.Thread(target=hold, args=(done,)) for done in release]
    for holder in holders:
        holder.start()
    for _ in range(LIMIT):
        assert inside.acquire(timeout=5)

    fourth_entered = threading.Event()
    fourth = threading.Thread(target=lambda: _enter_and_flag(fourth_entered))
    fourth.start()
    assert not fourth_entered.wait(WAIT_S)

    release[0].set()
    assert fourth_entered.wait(5)
    for done in release:
        done.set()
    for thread in [*holders, fourth]:
        thread.join()
    assert rds.zcard(KEY) == 0


def _enter_and_flag(entered: threading.Event) -> None:
    with _slot():
        entered.set()


def test_slots_of_holders_that_died_are_reclaimed_when_their_lease_runs_out() -> None:
    # Three holders whose process died: their leases expired long ago and nobody released them.
    rds.zadd(KEY, {f"dead-{i}": 1 for i in range(LIMIT)})

    with _slot():
        assert rds.zcard(KEY) == 1


def test_slot_is_released_when_the_block_raises() -> None:
    with pytest.raises(RuntimeError), _slot():
        raise RuntimeError("agent crashed")
    assert rds.zcard(KEY) == 0


def test_heartbeat_keeps_the_lease_alive_while_the_block_runs() -> None:
    with _slot():
        time.sleep(LEASE_S * 2.5)
        [(_, expires)] = rds.zrange(KEY, 0, -1, withscores=True)
        assert expires > _redis_now_ms()
