import logging
import threading
import traceback
from collections.abc import Callable

from redis import Redis
from redis.exceptions import RedisError

from .consumer import ack, read_one
from .dead_letter import dead_letter
from .job_event_kind import JobEventKind
from .lease import lease
from .reclaim import reclaim_one
from .work_loop_settings import WorkLoopSettings

FIRST_DELIVERY = 1
MS_PER_S = 1000
REDIS_RETRY_S = 5.0

type ReportStep = Callable[[str], None]  # step name: a multi-step job reports each step that passed
type Handle = Callable[[dict[str, str], ReportStep], None]  # raising leaves the job pending for a retry
# (entry id, kind, delivery, detail): the step name for `step`, the exception for `failed`, else None
type Observe = Callable[[str, JobEventKind, int, str | None], None]

logger = logging.getLogger(__name__)


def work_loop(
    client: Redis, settings: WorkLoopSettings, consumer: str, handle: Handle, stop: threading.Event, observe: Observe
) -> None:
    """Process jobs one at a time until `stop` is set; the current job always finishes first.

    Abandoned jobs (idle past the lease) come before new ones. A job delivered more than `max_deliveries`
    times is dead-lettered instead of run again. Every delivery, step and outcome goes to `observe`: Redis keeps
    only the job's current state, and forgets why it failed.
    """
    s = settings
    while not stop.is_set():
        try:
            entry = _next(client, s, consumer)
        except RedisError:
            # Seen on the host: the socket to Dockerized Redis drops while Redis is healthy. No job is leased yet,
            # so nothing is lost; dying here only costs a restart. redis-py reconnects on the next command.
            logger.warning("redis unreachable, retrying in %.0fs", REDIS_RETRY_S, exc_info=True)
            stop.wait(REDIS_RETRY_S)
            continue
        if entry is None:
            continue
        entry_id, fields, deliveries = entry
        if deliveries > s.max_deliveries:
            logger.error("job %s failed %d times; moving it to %s", entry_id, s.max_deliveries, s.dlq_stream)
            dead_letter(client, s.stream, s.group, entry_id, fields, s.dlq_stream)
            observe(entry_id, JobEventKind.dead_lettered, deliveries, None)
            continue
        observe(entry_id, JobEventKind.started, deliveries, None)
        try:
            with lease(client, s.stream, s.group, consumer, entry_id, s.lease_s):
                handle(fields, lambda step: observe(entry_id, JobEventKind.step, deliveries, step))
        except Exception as e:
            # No ack: the heartbeat has stopped, so the job is reclaimed once it has been idle for a lease.
            # That wait is the retry backoff.
            logger.exception("job %s failed (delivery %d of %d)", entry_id, deliveries, s.max_deliveries)
            observe(entry_id, JobEventKind.failed, deliveries, "".join(traceback.format_exception_only(e)).strip())
            continue
        ack(client, s.stream, s.group, entry_id)
        observe(entry_id, JobEventKind.done, deliveries, None)


def _next(client: Redis, s: WorkLoopSettings, consumer: str) -> tuple[str, dict[str, str], int] | None:
    reclaimed = reclaim_one(client, s.stream, s.group, consumer, int(s.lease_s * MS_PER_S))
    if reclaimed is not None:
        return reclaimed
    entry = read_one(client, s.stream, s.group, consumer, s.block_ms)
    return None if entry is None else (*entry, FIRST_DELIVERY)
