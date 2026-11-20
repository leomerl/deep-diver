import logging
import threading
from collections.abc import Callable

from redis import Redis

from .consumer import ack, read_one
from .dead_letter import dead_letter
from .lease import lease
from .reclaim import reclaim_one
from .work_loop_settings import WorkLoopSettings

FIRST_DELIVERY = 1
MS_PER_S = 1000

type Handle = Callable[[dict[str, str]], None]  # job fields -> done; raising leaves the job pending for a retry

logger = logging.getLogger(__name__)


def work_loop(client: Redis, settings: WorkLoopSettings, consumer: str, handle: Handle, stop: threading.Event) -> None:
    """Process jobs one at a time until `stop` is set; the current job always finishes first.

    Abandoned jobs (idle past the lease) come before new ones. A job delivered more than `max_deliveries`
    times is dead-lettered instead of run again.
    """
    s = settings
    while not stop.is_set():
        entry = _next(client, s, consumer)
        if entry is None:
            continue
        entry_id, fields, deliveries = entry
        if deliveries > s.max_deliveries:
            logger.error("job %s failed %d times; moving it to %s", entry_id, s.max_deliveries, s.dlq_stream)
            dead_letter(client, s.stream, s.group, entry_id, fields, s.dlq_stream)
            continue
        try:
            with lease(client, s.stream, s.group, consumer, entry_id, s.lease_s):
                handle(fields)
        except Exception:
            # No ack: the heartbeat has stopped, so the job is reclaimed once it has been idle for a lease.
            # That wait is the retry backoff.
            logger.exception("job %s failed (delivery %d of %d)", entry_id, deliveries, s.max_deliveries)
            continue
        ack(client, s.stream, s.group, entry_id)


def _next(client: Redis, s: WorkLoopSettings, consumer: str) -> tuple[str, dict[str, str], int] | None:
    reclaimed = reclaim_one(client, s.stream, s.group, consumer, int(s.lease_s * MS_PER_S))
    if reclaimed is not None:
        return reclaimed
    entry = read_one(client, s.stream, s.group, consumer, s.block_ms)
    return None if entry is None else (*entry, FIRST_DELIVERY)
