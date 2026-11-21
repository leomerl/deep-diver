import importlib
import threading
import time
from collections.abc import Callable, Iterator

import pytest
from redis.exceptions import TimeoutError

from app.config import rds
from app.queue import WorkLoopSettings, enqueue_once, ensure_group, work_loop

STREAM = "test:jobs"
DLQ = "test:dead"
GROUP = "test-group"
CONSUMER = "test-consumer"
DEDUP_KEY = "test:dedup:1"
MAX_DELIVERIES = 2
SETTINGS = WorkLoopSettings(
    stream=STREAM, group=GROUP, dlq_stream=DLQ, lease_s=0.1, max_deliveries=MAX_DELIVERIES, block_ms=10
)
DEADLINE_S = 5
# The package re-exports the function under the module's name, so the module needs an explicit import.
work_loop_module = importlib.import_module("app.queue.work_loop")
POLL_S = 0.02


@pytest.fixture(autouse=True)
def clean_redis() -> Iterator[None]:
    rds.flushdb()
    yield
    rds.flushdb()


def _run_in_background(handle: Callable[[dict[str, str]], None], stop: threading.Event) -> threading.Thread:
    ensure_group(rds, STREAM, GROUP)
    thread = threading.Thread(target=work_loop, args=(rds, SETTINGS, CONSUMER, handle, stop), daemon=True)
    thread.start()
    return thread


def test_success_is_acked() -> None:
    stop = threading.Event()
    seen: list[dict[str, str]] = []

    def handle(fields: dict[str, str]) -> None:
        seen.append(fields)
        stop.set()

    enqueue_once(rds, DEDUP_KEY, STREAM, {"payload": "x"})
    _run_in_background(handle, stop).join(DEADLINE_S)

    assert [f["payload"] for f in seen] == ["x"]
    assert rds.xpending(STREAM, GROUP)["pending"] == 0


def test_failing_job_is_retried_then_dead_lettered() -> None:
    stop = threading.Event()
    calls: list[int] = []

    def handle(fields: dict[str, str]) -> None:
        calls.append(1)
        raise RuntimeError("poison")

    enqueue_once(rds, DEDUP_KEY, STREAM, {"payload": "x"})
    thread = _run_in_background(handle, stop)
    deadline = time.monotonic() + DEADLINE_S
    while rds.xlen(DLQ) == 0 and time.monotonic() < deadline:
        time.sleep(POLL_S)
    stop.set()
    thread.join(DEADLINE_S)

    assert len(calls) == MAX_DELIVERIES
    assert rds.xlen(DLQ) == 1
    assert rds.xpending(STREAM, GROUP)["pending"] == 0
    assert rds.exists(DEDUP_KEY) == 0


def test_stop_ends_an_idle_loop() -> None:
    stop = threading.Event()
    thread = _run_in_background(lambda _: None, stop)
    stop.set()
    thread.join(DEADLINE_S)
    assert not thread.is_alive()


def test_redis_outage_is_retried_not_fatal(monkeypatch: pytest.MonkeyPatch) -> None:
    stop = threading.Event()
    attempts: list[int] = []

    def flaky_reclaim(*args: object) -> None:
        attempts.append(1)
        if len(attempts) == 1:
            raise TimeoutError("Timeout reading from socket")
        stop.set()

    monkeypatch.setattr(work_loop_module, "reclaim_one", flaky_reclaim)
    monkeypatch.setattr(work_loop_module, "REDIS_RETRY_S", 0)
    work_loop(rds, SETTINGS, CONSUMER, lambda fields: None, stop)

    assert len(attempts) == 2  # the loop came back after the error instead of propagating it
