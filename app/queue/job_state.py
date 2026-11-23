from enum import StrEnum


class JobState(StrEnum):
    """Where a job stands, derived from Redis alone (`stream_jobs`)."""

    queued = "queued"  # not delivered to the group yet
    running = "running"  # pending, and its lease is being renewed
    retrying = "retrying"  # pending but idle past the lease: it failed or its worker died; the reaper hands it out again
    done = "done"  # acked
    dead = "dead"  # dead-lettered
