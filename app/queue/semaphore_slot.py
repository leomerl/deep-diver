import logging
import random
import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from redis import Redis
from redis.commands.core import Script
from redis.exceptions import RedisError

_ACQUIRE = Path(__file__).with_name("semaphore_acquire.lua").read_text()
_RENEW = Path(__file__).with_name("semaphore_renew.lua").read_text()
RENEWALS_PER_LEASE = 3  # renew at a third of the lease, so one slow renewal doesn't lose the slot
JITTER = (0.5, 1.5)  # spreads retries, so waiting workers don't all hit Redis at the same instant
MS_PER_S = 1000

logger = logging.getLogger(__name__)


@contextmanager
def semaphore_slot(client: Redis, key: str, limit: int, lease_s: float, poll_s: float) -> Iterator[None]:
    """Hold one of `limit` slots shared by every process that uses `key`, for as long as the block runs.

    Waits, polling with jitter, until a slot is free. The slot is a lease renewed in the background, so a
    process that dies without releasing it frees the slot once the lease runs out.
    """
    token = uuid.uuid4().hex
    lease_ms = int(lease_s * MS_PER_S)
    acquire = client.register_script(_ACQUIRE)
    while not acquire(keys=[key], args=[token, limit, lease_ms]):
        time.sleep(poll_s * random.uniform(*JITTER))
    released = threading.Event()
    heartbeat = threading.Thread(
        target=_renew_until_released,
        args=(client.register_script(_RENEW), key, token, lease_ms, lease_s / RENEWALS_PER_LEASE, released),
        daemon=True,
    )
    heartbeat.start()
    try:
        yield
    finally:
        released.set()
        heartbeat.join()
        client.zrem(key, token)


def _renew_until_released(
    renew: Script, key: str, token: str, lease_ms: int, every_s: float, released: threading.Event
) -> None:
    while not released.wait(every_s):
        try:
            if not renew(keys=[key], args=[token, lease_ms]):
                # The process stalled past its lease, so someone else may hold the slot now. Stopping the agent
                # would waste its work; running one over the limit until it ends is the smaller harm.
                logger.warning("semaphore %s: lease %s ran out; running over the limit until done", key, token)
                return
        except RedisError:
            # Keep trying: the lease outlasts a short Redis blip.
            logger.warning("semaphore %s: renewing %s failed", key, token, exc_info=True)
