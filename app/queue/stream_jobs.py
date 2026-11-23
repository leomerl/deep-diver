from dataclasses import dataclass

from redis import Redis

from .fields import ORIGINAL_ID_FIELD
from .job_state import JobState

# shortcut: one page of the pending list and the whole DLQ are read per call; fine while both stay in the tens.
# Upgrade: page XPENDING by id range, and index the DLQ by original id.
PENDING_SCAN = 100


@dataclass(frozen=True)
class StreamJob:
    entry_id: str
    fields: dict[str, str]
    state: JobState
    deliveries: int | None  # known only while pending: Redis drops the count on ack
    consumer: str | None  # the worker holding it while pending


def stream_jobs(client: Redis, stream: str, group: str, dlq_stream: str, lease_ms: int, count: int) -> list[StreamJob]:
    """The stream's newest `count` jobs, newest first. Acked entries stay in the stream (nothing trims it), so the
    stream is the job history: pending is running or retrying, in the DLQ is dead, past the group's cursor is
    queued, the rest is done."""
    if not client.exists(stream):  # no job was ever queued
        return []
    entries = client.xrevrange(stream, count=count)
    cursor = next((g["last-delivered-id"] for g in client.xinfo_groups(stream) if g["name"] == group), None)
    if cursor is None:  # queued before any worker created the group: nothing was delivered
        return [StreamJob(entry_id, fields, JobState.queued, None, None) for entry_id, fields in entries]
    pending = {p["message_id"]: p for p in client.xpending_range(stream, group, "-", "+", PENDING_SCAN)}
    dead = {fields[ORIGINAL_ID_FIELD] for _, fields in client.xrange(dlq_stream) if ORIGINAL_ID_FIELD in fields}

    def job(entry_id: str, fields: dict[str, str]) -> StreamJob:
        p = pending.get(entry_id)
        if p is not None:
            state = JobState.running if p["time_since_delivered"] < lease_ms else JobState.retrying
            return StreamJob(entry_id, fields, state, p["times_delivered"], p["consumer"])
        if entry_id in dead:
            return StreamJob(entry_id, fields, JobState.dead, None, None)
        queued = _order(entry_id) > _order(cursor)
        return StreamJob(entry_id, fields, JobState.queued if queued else JobState.done, None, None)

    return [job(entry_id, fields) for entry_id, fields in entries]


def _order(entry_id: str) -> tuple[int, int]:
    """Entry ids are `<ms>-<seq>`; compared as strings, "10-0" would sort before "9-0"."""
    ms, seq = entry_id.split("-")
    return int(ms), int(seq)
