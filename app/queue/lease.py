import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from redis import Redis
from redis.commands.core import Script
from redis.exceptions import RedisError

_RENEW = Path(__file__).with_name("lease_renew.lua").read_text()
RENEWALS_PER_LEASE = 3  # renew at a third of the lease, so one slow renewal doesn't lose the job

logger = logging.getLogger(__name__)


@contextmanager
def lease(client: Redis, stream: str, group: str, consumer: str, entry_id: str, lease_s: float) -> Iterator[None]:
    """Keep a pending entry's idle time low while the block runs, so the reaper leaves it alone."""
    done = threading.Event()
    heartbeat = threading.Thread(
        target=_renew_until_done,
        args=(client.register_script(_RENEW), stream, group, consumer, entry_id, lease_s / RENEWALS_PER_LEASE, done),
        daemon=True,
    )
    heartbeat.start()
    try:
        yield
    finally:
        done.set()
        heartbeat.join()


def _renew_until_done(
    renew: Script, stream: str, group: str, consumer: str, entry_id: str, every_s: float, done: threading.Event
) -> None:
    while not done.wait(every_s):
        try:
            if not renew(keys=[stream], args=[group, consumer, entry_id]):
                # We stalled past the lease and another worker took the job. Both runs end in an insert-once
                # write, so finishing ours costs money, not data; stopping it would waste the work done so far.
                logger.warning("lease on %s %s lost to another consumer; finishing anyway", stream, entry_id)
                return
        except RedisError:
            # Keep trying: the lease outlasts a short Redis blip.
            logger.warning("lease on %s %s: renewing failed", stream, entry_id, exc_info=True)
